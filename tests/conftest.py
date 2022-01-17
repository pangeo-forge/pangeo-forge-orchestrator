import copy
import os
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Tuple

import pytest
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session

from pangeo_forge_orchestrator.model_builders import MultipleModels
from pangeo_forge_orchestrator.models import MODELS

from .interfaces import clear_table

# Helpers ---------------------------------------------------------------------------------


def get_open_port():
    heroku_port = os.environ.get("PORT", False)
    if heroku_port:

        return heroku_port
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
        "--log-level=info",
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

    # sqlite_file_path = f"sqlite:////{tempdir}/database.db"
    # connect_args = {"check_same_thread": False}
    # engine = create_engine(sqlite_file_path, echo=True, connect_args=connect_args)
    from pangeo_forge_orchestrator.database import engine

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
                run_date="2021-01-01T00:00:00Z",
                bakery_id=0,
                feedstock_id=0,
                commit="012345abcdefg",
                version="1.0",
                status="complete",
            ),
            blank_opts=["message"],
        ),
        ModelKwargs(
            request=dict(
                recipe_id="test-recipe-1",
                run_date="2021-02-02T00:00:00Z",
                bakery_id=1,
                feedstock_id=1,
                commit="012345abcdefg",
                version="2.0",
                status="complete",
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
    def model_to_create(self, models_with_kwargs):
        kw_0, _ = models_with_kwargs.kwargs
        return models_with_kwargs.models, kw_0.request, kw_0.blank_opts


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
        key = list(different_kws)[0]
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
