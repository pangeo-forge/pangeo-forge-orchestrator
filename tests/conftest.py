import copy
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Tuple

import pytest
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, create_engine

from pangeo_forge_orchestrator.abstractions import MultipleModels
from pangeo_forge_orchestrator.models import MODELS, RecipeRunConclusion, RecipeRunStatus

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


@dataclass
class ModelKwargs:
    """Container to hold kwargs for instantiating ``SQLModel`` table model.

    :param request: The kwargs for instantatiting a table model. Can be passed to a model object
    in the Python context, or sent as JSON to the database API.
    :param blank_opts: List of any optional model fields which are excluded from the ``request``.
    """

    request: dict
    blank_opts: List[str] = field(default_factory=list)


@dataclass
class ModelFixture:
    """Container for a ``MultipleModels`` object (itself containing ``SQLModel`` objects) with
    kwargs which can be used to instantiate the models within it.

    :param models: A ``MultipleModels`` object.
    :param kwargs: A 2-tuple consisting of two ``ModelKwargs`` objects matched to the ``models``.
      Note that two sets of kwargs are required because: (1) the ``read_range`` test requires
      that more than one entry is populated into the database; and (2) the ``update`` test requires
      that we have have an additional set of kwargs with which to update a database entry.
    """

    models: MultipleModels
    kwargs: Tuple[ModelKwargs, ModelKwargs]

    def __post_init__(self):
        if len(self.kwargs) != 2:
            raise ValueError("``len(self.kwargs)`` must equal 2.")


# To test additional models:
#   1. Add a session-scoped fixture here which returns a `ModelFixture`, the name of which should
#      be `model_key_with_kwargs`, where `model_key` is the name of the key mapping for the
#      associated `MultipleModels` object in the `pangeo_forge_orchestrator.models::MODELS` dict.
#   2. Add `lazy_fixture("model_key_with_kwargs")` to the param list of the `models_with_kwargs`
#      fixture. (Where `"model_key_with_kwargs"` is the name of the fixture you created in step 1.)


@pytest.fixture(scope="session")
def recipe_run_with_kwargs():
    kws = [
        ModelKwargs(
            request=dict(
                recipe_id="test-recipe-0",
                bakery_id=0,
                feedstock_id=0,
                head_sha="012345abcdefg",
                version="1.0",
                path="/path-to-dataset.zarr",
                started_at="2021-01-01T00:00:00Z",
                completed_at="2021-01-01T01:01:01Z",
                conclusion="success",
                status="queued",
            ),
            blank_opts=["message"],
        ),
        ModelKwargs(
            request=dict(
                recipe_id="test-recipe-1",
                bakery_id=1,
                feedstock_id=1,
                head_sha="012345abcdefg",
                version="2.0",
                path="/path-to-dataset.zarr",
                started_at="2021-02-02T00:00:00Z",
                completed_at="2021-02-02T02:02:02Z",
                conclusion="success",
                status="queued",
                message="hello",
            ),
        ),
    ]
    return ModelFixture(MODELS["recipe_run"], kws)


@pytest.fixture(
    scope="session", params=[lazy_fixture("recipe_run_with_kwargs")],
)
def models_with_kwargs(request):
    return request.param


# CRUD function fixtures ------------------------------------------------------------------

# Create ----------------------------------------------------------------------------------


class CreateFixtures:
    """Fixtures for ``TestCreate``"""

    @pytest.fixture
    def model_to_create(self, models_with_kwargs: ModelFixture):
        kw_0, _ = models_with_kwargs.kwargs
        return models_with_kwargs.models, kw_0.request, kw_0.blank_opts

    @pytest.fixture(params=["incomplete", "invalid"])
    def failing_model_to_create(self, model_to_create: ModelFixture, request):
        failure_mode = request.param
        models, request, _ = model_to_create
        failing_request = copy.deepcopy(request)

        if failure_mode == "incomplete":
            del failing_request[next(iter(failing_request))]  # Remove a required field
        elif failure_mode == "invalid":
            assert type(request[next(iter(request))]) == str
            failing_request[next(iter(failing_request))] = {"message": "Is this wrong?"}
            assert type(failing_request[next(iter(failing_request))]) == dict

        return models, failing_request, failure_mode


# Read ------------------------------------------------------------------------------------


class ReadFixtures:
    """Fixtures for ``TestRead``"""

    @pytest.fixture
    def models_to_read(self, models_with_kwargs: ModelFixture):
        models = models_with_kwargs.models
        kw_0, kw_1 = models_with_kwargs.kwargs
        model_0 = models.table(**kw_0.request)
        model_1 = models.table(**kw_1.request)
        return models, (model_0, model_1)

    @pytest.fixture
    def single_model_to_read(self, models_with_kwargs: ModelFixture):
        models = models_with_kwargs.models
        _, kw_1 = models_with_kwargs.kwargs
        table = models.table(**kw_1.request)
        return models, table


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


# Delete --------------------------------------------------------------------------------


class DeleteFixtures:
    """Fixtures for ``TestDelete``"""

    @pytest.fixture
    def model_to_delete(self, models_with_kwargs):
        models = models_with_kwargs.models
        kw_0, _ = models_with_kwargs.kwargs
        table = models.table(**kw_0.request)
        return models, table


# Specific constrained types ------------------------------------------------------------


class EnumFixtureFactory:
    """A mixin of fixture definition methods. In subclasses, these methods are used to define
    fixtures for testing type validation of (``enum``-based) categorical database fields.
    """

    failure_mode = "enum"  # Used to select error class in `test_database.CreateLogic.get_error`

    def make_model_to_create(
        self, model_fixture: ModelFixture, request,
    ) -> Tuple[MultipleModels, dict, list]:
        """Make a fixture for use with ``test_database.CreateLogic.test_create``.

        :param model_fixture: The ``ModelFixture`` object. Note that the generic fixtures (defined
          in ``CreateFixtures``) use a lazy fixture (``models_with_kwargs``) which represents a
          parametrization of all models in the ``pangeo_forge_orchestrator.models.MODELS`` dict.
          By contrast, fixture classes which inherit from this mixin will pass only the single,
          specific ``ModelFixture`` representing the database model in which the targeted
          categorical field exists.
        :param request: The pytest request object containing a parametrization of all valid options
          for the categorical field. E.g.: ``@pytest.fixture(params=[opt.value for opt in Obj])``,
          where ``Obj`` is the ``enum`` object that defines the categorical options to test.
        """

        kw_0, _ = model_fixture.kwargs
        kw_0.request[self.field_name] = request.param
        return model_fixture.models, kw_0.request, kw_0.blank_opts

    def make_failing_model_to_create(
        self, model_fixture: ModelFixture
    ) -> Tuple[MultipleModels, dict, str]:
        """Make a fixture for use with ``test_database.CreateLogic.test_create_failure``.

        :param model_fixture: The ``ModelFixture`` object. See docstring for
          ``make_model_to_create`` method on this class for full description.
        """
        kw_0, _ = model_fixture.kwargs
        failing_request = copy.deepcopy(kw_0.request)
        failing_request[self.field_name] = self.invalid_value
        return model_fixture.models, failing_request, self.failure_mode


class RecipeRunStatusFixtures(EnumFixtureFactory):
    """Fixtures for testing validation of values passed to recipe run table's `status` field.
    """

    field_name = "status"
    invalid_value = "invalid_status"

    @pytest.fixture(params=[opt.value for opt in RecipeRunStatus])
    def model_to_create(self, recipe_run_with_kwargs: ModelFixture, request):
        return self.make_model_to_create(recipe_run_with_kwargs, request)

    @pytest.fixture
    def failing_model_to_create(self, recipe_run_with_kwargs: ModelFixture):
        return self.make_failing_model_to_create(recipe_run_with_kwargs)


class RecipeRunConclusionFixtures(EnumFixtureFactory):
    """Fixtures for testing validation of values passed to recipe run table's `conclusion` field.
    """

    field_name = "conclusion"
    invalid_value = "invalid_conclusion"

    @pytest.fixture(params=[opt.value for opt in RecipeRunConclusion])
    def model_to_create(self, recipe_run_with_kwargs: ModelFixture, request):
        return self.make_model_to_create(recipe_run_with_kwargs, request)

    @pytest.fixture
    def failing_model_to_create(self, recipe_run_with_kwargs: ModelFixture):
        return self.make_failing_model_to_create(recipe_run_with_kwargs)
