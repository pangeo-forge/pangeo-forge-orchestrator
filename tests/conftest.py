import copy
import socket
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pytest
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, create_engine

from pangeo_forge_orchestrator.abstractions import MultipleModels
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
    engine = create_engine(sqlite_file_path, echo=True, connect_args=connect_args)
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


class APIErrors(str, Enum):
    """
    """

    datetime = "datetime"  # ISO 8601
    enum = "enum"
    int = "integer"
    missing = "missing"
    str = "string"


@dataclass
class SuccessKwargs:
    """Container to hold kwargs for instantiating ``SQLModel`` table model.

    :param success: The kwargs for instantatiting a table model. Can be passed to a model object
    in the Python context, or sent as JSON to the database API.
    :param failure:
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
                "On instantiation of `SuccessKwargs`, the following values in `self.every_field` "
                f"and `self.no_optionals` were found to be equivalent: {overlap}. All values in "
                "these two dicts must be distinct."
            )


@dataclass
class FailureKwargs:
    """

    """

    update_with: dict
    raises: APIErrors


@dataclass
class ModelWithKwargs:
    """Container for a ``MultipleModels`` object (itself containing ``SQLModel`` objects) with
    kwargs which can be used to instantiate the models within it.

    :param models: A ``MultipleModels`` object.
    :param success_kws: A 2-tuple consisting of two ``ModelKwargs`` objects matched to the
      ``models``. Note that two sets of kwargs are required because: (1) the ``read_range`` test
      requires that more than one entry is populated into the database; and (2) the ``update``
      test requires that we have have an additional set of kwargs with which to update an entry.
    :param failure_kws:
    """

    models: MultipleModels
    success_kws: SuccessKwargs
    failure_kws: Optional[FailureKwargs] = None


# To test additional models:
#   1. Add a session-scoped fixture here which returns a `ModelFixture`, the name of which should
#      be `model_key_with_kwargs`, where `model_key` is the name of the key mapping for the
#      associated `MultipleModels` object in the `pangeo_forge_orchestrator.models::MODELS` dict.
#   2. Add `lazy_fixture("model_key_with_kwargs")` to the param list of the `models_with_kwargs`
#      fixture. (Where `"model_key_with_kwargs"` is the name of the fixture you created in step 1.)
#
# NOTE: Because Pydantic parses things, we need to be careful
#

NOT_STR = {"not parsable": "to str"}
NOT_INT = "not parsable to int"
NOT_ISO8601 = "Jan 01 2021 00:00:00"


class RecipeRunFixtures:
    """
    """

    models = MODELS["recipe_run"]

    @pytest.fixture(
        scope="session",
        params=[
            (dict(recipe_id=NOT_STR), APIErrors.str),
            (dict(bakery_id=NOT_INT), APIErrors.int),
            (dict(feedstock_id=NOT_INT), APIErrors.int),
            (dict(head_sha=NOT_STR), APIErrors.str),
            (dict(version=NOT_STR), APIErrors.str),  # TODO: use `ConstrainedStr`
            (dict(path=NOT_STR), APIErrors.str),
            (dict(started_at=NOT_ISO8601), APIErrors.datetime),
            (dict(completed_at=NOT_ISO8601), APIErrors.datetime),
            (dict(conclusion="not a valid conclusion"), APIErrors.enum),
            (dict(status="not a valid status"), APIErrors.enum),
            (dict(message=NOT_STR), APIErrors.str),
            # TODO: Add invalid pairs of fields.
        ],
    )
    def failure_kws_recipe_run(self, request):
        """

        """
        update_with, raises = request.param
        return FailureKwargs(update_with, raises)

    @pytest.fixture(scope="session")
    def success_kws_recipe_run(self) -> SuccessKwargs:
        """

        """
        success_kwargs = SuccessKwargs(
            all=dict(
                recipe_id="test-recipe-0",
                bakery_id=0,
                feedstock_id=0,
                head_sha="abcdefg12345",
                version="1.0",
                path="/path-to-dataset.zarr",
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
                path="/path-to-another-dataset.zarr",
                started_at="2021-02-02T00:00:00Z",
                status="queued",
            ),
        )
        return success_kwargs

    @pytest.fixture
    def recipe_run_success_only_model(
        self, success_kws_recipe_run: SuccessKwargs
    ) -> ModelWithKwargs:
        """
        """
        return ModelWithKwargs(self.models, success_kws_recipe_run)

    @pytest.fixture
    def recipe_run_complete_model(
        self, success_kws_recipe_run: SuccessKwargs, failure_kws_recipe_run: FailureKwargs,
    ) -> ModelWithKwargs:
        """
        """
        return ModelWithKwargs(self.models, success_kws_recipe_run, failure_kws_recipe_run)


class ModelFixtures(RecipeRunFixtures):
    """
    """

    @pytest.fixture(
        scope="session", params=[lazy_fixture("recipe_run_success_only_model")],
    )
    def success_only_models(self, request) -> ModelWithKwargs:
        return request.param

    @pytest.fixture(
        scope="session", params=[lazy_fixture("recipe_run_complete_model")],
    )
    def complete_models(self, request) -> ModelWithKwargs:
        return request.param


# CRUD function fixtures ------------------------------------------------------------------

# Update --------------------------------------------------------------------------------


class UpdateFixtures:
    """Fixtures for ``TestUpdate``"""

    @pytest.fixture(scope="session")
    def model_to_update(self, models_with_kwargs):
        models = models_with_kwargs.models
        kw_0, kw_1 = models_with_kwargs.kwargs
        table = models.table(**kw_0.request)
        different_kws = copy.deepcopy(kw_1.request)
        key = next(iter(different_kws))
        update_with = {key: different_kws.pop(key)}
        return models, table, update_with
