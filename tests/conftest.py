import socket
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pytest
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, create_engine

from pangeo_forge_orchestrator.model_builders import MultipleModels
from pangeo_forge_orchestrator.models import MODELS

from .interfaces import clear_table

# Helpers ---------------------------------------------------------------------------------


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


def start_http_server(path, request):
    port = get_open_port()
    command_list = [
        "uvicorn",
        "pangeo_forge_orchestrator.api:api",
        f"--port={port}",
        "--log-level=critical",
    ]
    p = subprocess.Popen(command_list, cwd=path)
    url = f"http://127.0.0.1:{port}"
    time.sleep(1)  # let the server start up

    def teardown():
        p.kill()

    request.addfinalizer(teardown)

    return url


# General fixtures ------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tempdir(tmp_path_factory):
    return tmp_path_factory.mktemp("test-database")


@pytest.fixture(scope="session")
def http_server_url(tempdir, request):
    url = start_http_server(tempdir, request=request)
    return url


@pytest.fixture
def uncleared_session(tempdir):
    # Cf. `pangeo_forge_orchestrator.database` & `pangeo_forge_orchestrator.api`
    # Here we are creating a session for the database file which exists in the tempdir.
    # We can't reuse the `pangeo_forge_orchestrator.api:get_session` function here because
    # the session returned by that function resolves the database path via `os.getcwd()`, but
    # our tests are run from a different working directory than the one where the database resides.
    sqlite_file_path = f"sqlite:////{tempdir}/database.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(sqlite_file_path, echo=False, connect_args=connect_args)
    with Session(engine) as session:
        yield session


@pytest.fixture
def session(uncleared_session):
    with uncleared_session as session:
        for k in MODELS.keys():
            clear_table(session, MODELS[k].table)  # make sure the database is empty
        yield session


@pytest.fixture
def http_server(http_server_url, session):
    for k in MODELS.keys():
        clear_table(session, MODELS[k].table)  # make sure the database is empty
    return http_server_url


# Models --------------------------------------------------------------------------------

# Model fixture containers --------------------------------------------------------------


class APIErrors(str, Enum):
    """Error types that may occur if field input does not conform to the schema defined by the
    table's Pydantic base model.
    """

    datetime = "datetime"
    enum = "enum"
    int = "integer"
    missing = "missing"
    str = "string"


@dataclass
class SuccessKwargs:
    """Container to hold kwargs for instantiating ``SQLModel`` table model. Can be passed to a
    model object in the Python context, or sent as JSON to the database API. As indicated by the
    ``__post_init__`` method of this class, for all keys present in both kwargs dictionaries, there
    cannot be any overlap in values. This ensures that tests which use both sets of kwargs (i.e.,
    read range and update tests) have distinct values to work with for each of the shared keys.

    :param all: This dict should contain a key:value pair for all fields (required & optional).
    :param reqs_only: This dict should contain a key:value pair only for required fields.
    """

    all: dict
    reqs_only: dict

    def __post_init__(self):
        overlap = {
            k: v
            for k, v in self.all.items()
            if k in self.reqs_only.keys() and self.reqs_only[k] == v
        }
        if overlap:
            raise ValueError(
                "On instantiation of `SuccessKwargs`, the following values in `self.all` and "
                f"`self.reqs_only` were found to be equivalent: {overlap}. All values in these "
                "two dicts must be distinct."
            )


@dataclass
class FailureKwargs:
    """Container to hold kwargs for a ``SQLModel`` which will cause a known failure (i.e. type
    validation error) to occur. Note that the ``update_with`` dict is not a complete set of
    kwargs for instantiating the ``SQLModel``, but rather the minimal set of kwargs which, if used
    to update a ``SuccessKwargs.all`` dict, would cause the error specified by ``raises`` to occur.

    :param update_with: A dictionary which will cause a known type validation error to occur. This
      is likely to be only a single key:value pair, where the value provided is known to be of not
      parseable into a valid type for the field specified by the key. In (less common) situations
      where the validation error is caused by interrelationships of model fields, this dictionary
      may contain more than one key:value pair.
    :param raises: The error type raised by passing the kwargs provided in ``update_with``. Note
      that this is not the actual Python exception class, but rather a categorical option from the
      ``APIErrors`` class. This is because different interfaces (client, CLI, etc.) raise different
      exception classes when the same failure mode is encountered.
    """

    update_with: dict
    raises: APIErrors


@dataclass
class ModelWithKwargs:
    """Container for a ``MultipleModels`` object (itself containing ``SQLModel`` objects) with
    kwargs which can be used to successfully instantiate the models within it, as well as kwargs
    which will cause known failures to occur.

    :param models: A ``MultipleModels`` object cooresponding to the table to test.
    :param success_kws: A ``SuccessKwargs`` object cooresponding to the table to test.
    :param failure_kws: A ``FailureKwargs`` object cooresponding to the table to test.
    """

    models: MultipleModels
    success_kws: SuccessKwargs
    failure_kws: Optional[FailureKwargs] = None


# Specific model fixtures ---------------------------------------------------------------
#
# To test additional models:
#   1. Add a `ModelNameFixtures` object below, following the template provided by the
#      `RecipeRunFixtures` object.
#   2. Add the `ModelNameFixtures` as a subclass of of the `ModelFixtures` object below.
#
# NOTE: The constants defined below can be used for instantiating `FailureKwargs` objects
# with values which cannot be parsed by Pydantic to a given type. Because Pydantic parses
# input fields, it is not sufficient for a given input to be of a different Python type;
# for example, the int `1` can be parsed by Pydantic as `str(1)`.

NOT_STR = {"not parsable": "to str"}
NOT_INT = "not parsable to int"
NOT_ISO8601 = "Jan 01 2021 00:00:00"


class RecipeRunFixtures:
    """Container for fixtures for testing the ``RecipeRun`` model. Also serves as a template for
    fixtures classes for other models. Note that all such fixture classes must include:
        1. A ``models`` attribute defining the cooresponding ``MultipleModels`` object in the
           ``pangeo_forge_orchestrator.models.MODELS`` dict.
        2. A ``failure_kws_model_name`` session-scoped fixture, parametrized to return as many
           ``FailureKwargs`` objects as you would like to test for the given model.
        3. A ``success_kws_model_name`` session-scoped fixture, returning a ``SuccessKwargs``
           object cooresponding to the model.
        4. A ``model_name_success_only_model`` session-scoped fixture, returning a
           ``ModelWithKwargs`` object instantiated with the ``models`` attribute and the
           ``success_kws_model_name`` fixture.
        5. A ``model_name_complete_model`` session-scoped fixture, returning a ``ModelWithKwargs``
           object instantiated with the ``models`` attribute, the ``success_kws_model_name``
           fixture, and the ``failure_kws_model_name`` fixture.
    """

    @pytest.fixture(
        scope="session",
        params=[
            (dict(recipe_id=NOT_STR), APIErrors.str),
            (dict(bakery_id=NOT_INT), APIErrors.int),
            (dict(feedstock_id=NOT_INT), APIErrors.int),
            (dict(head_sha=NOT_STR), APIErrors.str),
            (dict(version=NOT_STR), APIErrors.str),  # TODO: use `ConstrainedStr`
            (dict(started_at=NOT_ISO8601), APIErrors.datetime),
            (dict(completed_at=NOT_ISO8601), APIErrors.datetime),
            (dict(conclusion="not a valid conclusion"), APIErrors.enum),
            (dict(status="not a valid status"), APIErrors.enum),
            (dict(message=NOT_STR), APIErrors.str),
            # TODO: Add invalid pairs of fields; e.g. `status=completed` w/ `conclusion=None`.
        ],
    )
    def failure_kws_recipe_run(self, request):
        """A parametrized fixture of ``FailureKwargs`` objects covering all known failure modes of
        the ``RecipeRun`` model.
        """

        update_with, raises = request.param
        return FailureKwargs(update_with, raises)

    @pytest.fixture(scope="session")
    def success_kws_recipe_run(self) -> SuccessKwargs:
        """A ``SuccessKwargs`` object for the ``RecipeRun`` model, inclusive of an ``.all`` dict
        containing valid values for all fields, as well as a ``.reqs_only`` dict containing only
        required fields. Note that for shared keys, all values are distinct (this is enforced by
        the ``__post_init__`` method of ``SucessKwargs``).
        """

        success_kwargs = SuccessKwargs(
            all=dict(
                recipe_id="test-recipe-0",
                bakery_id=0,
                feedstock_id=0,
                head_sha="abcdefg12345",
                version="1.0",
                started_at="2021-01-01T00:00:00Z",
                completed_at="2021-01-01T01:01:01Z",
                conclusion="success",
                status="completed",
                message="hello",
            ),
            reqs_only=dict(
                recipe_id="test-recipe-1",
                bakery_id=1,
                feedstock_id=1,
                head_sha="012345abcdefg",
                version="2.0",
                started_at="2021-02-02T00:00:00Z",
                status="queued",
            ),
        )
        return success_kwargs

    @pytest.fixture
    def recipe_run_success_only_model(
        self, success_kws_recipe_run: SuccessKwargs
    ) -> ModelWithKwargs:
        """A ``ModelWithKwargs`` object for ``RecipeRun`` omitting the optional failure kwargs.
        """
        return ModelWithKwargs(MODELS["recipe_run"], success_kws_recipe_run)

    @pytest.fixture
    def recipe_run_complete_model(
        self, success_kws_recipe_run: SuccessKwargs, failure_kws_recipe_run: FailureKwargs,
    ) -> ModelWithKwargs:
        """A ``ModelWithKwargs`` object for ``RecipeRun`` including the optional failure kwargs.
        """
        return ModelWithKwargs(MODELS["recipe_run"], success_kws_recipe_run, failure_kws_recipe_run)


class BakeryFixtures:
    """
    """

    @pytest.fixture(
        scope="session",
        params=[
            (dict(region=NOT_STR), APIErrors.str),
            (dict(name=NOT_STR), APIErrors.str),
            (dict(description=NOT_STR), APIErrors.str),
        ],
    )
    def failure_kws_bakery(self, request):
        """A parametrized fixture of ``FailureKwargs`` objects covering all known failure modes of
        the ``Bakery`` model.
        """

        update_with, raises = request.param
        return FailureKwargs(update_with, raises)

    @pytest.fixture(scope="session")
    def success_kws_bakery(self) -> SuccessKwargs:
        """A ``SuccessKwargs`` object for the ``Bakery`` model, inclusive of an ``.all`` dict
        containing valid values for all fields, as well as a ``.reqs_only`` dict containing only
        required fields. Note that for shared keys, all values are distinct (this is enforced by
        the ``__post_init__`` method of ``SucessKwargs``).
        """

        success_kwargs = SuccessKwargs(
            all=dict(region="a", name="b", description="c",),
            reqs_only=dict(region="d", name="e", description="f",),
        )
        return success_kwargs

    @pytest.fixture
    def bakery_success_only_model(self, success_kws_bakery: SuccessKwargs) -> ModelWithKwargs:
        """A ``ModelWithKwargs`` object for ``Bakery`` omitting the optional failure kwargs.
        """
        return ModelWithKwargs(MODELS["bakery"], success_kws_bakery)

    @pytest.fixture
    def bakery_complete_model(
        self, success_kws_bakery: SuccessKwargs, failure_kws_bakery: FailureKwargs,
    ) -> ModelWithKwargs:
        """A ``ModelWithKwargs`` object for ``Bakery`` including the optional failure kwargs.
        """
        return ModelWithKwargs(MODELS["bakery"], success_kws_bakery, failure_kws_bakery)


class ModelFixtures(RecipeRunFixtures, BakeryFixtures):
    """A container of lazy fixtures for all models to test. To add a model, add its cooresponding
    fixtures class as a subclass; e.g., ``ModelFixtures(RecipeRunFixtures, ModelNameFixtures)``.
    Then add ``lazy_fixture("model_name_success_only_model")`` fixture to the params list of
    ``sucess_only_models`` and ``lazy_fixture("model_name_complete_model")`` to the params list
    of ``complete_models``.
    """

    @pytest.fixture(
        scope="session",
        params=[
            lazy_fixture("recipe_run_success_only_model"),
            lazy_fixture("bakery_success_only_model"),
        ],
    )
    def success_only_models(self, request) -> ModelWithKwargs:
        return request.param

    @pytest.fixture(
        scope="session",
        params=[lazy_fixture("recipe_run_complete_model"), lazy_fixture("bakery_complete_model")],
    )
    def complete_models(self, request) -> ModelWithKwargs:
        return request.param
