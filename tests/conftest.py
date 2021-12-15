import ast
import copy
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional

import pytest
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel, create_engine

import pangeo_forge_orchestrator.abstractions as abstractions
from pangeo_forge_orchestrator.abstractions import MultipleModels
from pangeo_forge_orchestrator.client import Client
from pangeo_forge_orchestrator.models import MODELS

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


def commit_to_session(session: Session, model: SQLModel):
    session.add(model)
    session.commit()


class _MissingFieldError(Exception):
    pass


class _TypeError(Exception):
    pass


def get_data_from_cli(
    request_type: str, database_url: str, endpoint: str, request: Optional[dict] = None,
):
    os.environ["PANGEO_FORGE_DATABASE_URL"] = database_url
    cmd = ["pangeo-forge", "database", request_type, endpoint]
    if request is not None:
        cmd.append(json.dumps(request))
    stdout = subprocess.check_output(cmd)
    data = ast.literal_eval(stdout.decode("utf-8"))
    if isinstance(data, dict) and "detail" in data.keys():
        error = data["detail"][0]
        if isinstance(error, dict):
            if error["msg"] == "field required" and error["type"] == "value_error.missing":
                raise _MissingFieldError
            elif "type expected" in error["msg"] and "type_error." in error["type"]:
                raise _TypeError
    return data


# General ---------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tempdir(tmp_path_factory):
    return tmp_path_factory.mktemp("test-database")


@pytest.fixture(scope="session")
def http_server(tempdir, request):
    url = start_http_server(tempdir, request=request)
    return url


@pytest.fixture
def session(tempdir):
    # Cf. `pangeo_forge_orchestrator.database` & `pangeo_forge_orchestrator.api`
    # Here we are creating a session for the database file which exists in the tempdir.
    # We can't reuse the `pangeo_forge_orchestrator.api:get_session` function here because
    # the session returned by that function resolves the database path via `os.getcwd()`, but
    # our tests are run from a different workind directory than the one where the database resides.
    sqlite_file_path = f"sqlite:////{tempdir}/database.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(sqlite_file_path, echo=True, connect_args=connect_args)
    with Session(engine) as session:
        yield session


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
    kwargs which can be used to instiate the models within it.

    :param models: A ``MultipleModels`` object.
    :param kwargs: A list of three ``ModelKwargs`` objects matched to the ``models``.
    """

    models: MultipleModels
    kwargs: List[ModelKwargs]

    def __post_init__(self):
        if len(self.kwargs) != 3:
            raise ValueError("``len(self.kwargs)`` must equal 3.")


# To test additional models:
#   1. Add a session-scoped fixture here which returns a `ModelFixture`, the name of which should
#      be `model_key_with_kwargs`, where `model_key` is the name of the key mapping for the
#      associated `MultipleModels` object in the `pangeo_forge_orchestrator.models::MODELS` dict.
#   2. Add `lazy_fixture("model_key_with_kwargs")` to the param list of the `models_with_kwargs`
#      fixture. (Where `"model_key_with_kwargs"` is the name of the fixture you created un steo 1.)


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
                path="/path-to-dataset.zarr",
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
                path="/path-to-dataset.zarr",
                message="hello",
            ),
        ),
        ModelKwargs(
            request=dict(
                recipe_id="test-recipe-2",
                run_date="2021-03-03T00:00:00Z",
                bakery_id=2,
                feedstock_id=2,
                commit="012345abcdefg",
                version="3.0",
                status="complete",
                path="/path-to-dataset.zarr",
            ),
            blank_opts=["message"],
        ),
    ]
    return ModelFixture(MODELS["recipe_run"], kws)


@pytest.fixture(
    scope="session", params=[lazy_fixture("recipe_run_with_kwargs")],
)
def models_with_kwargs(request):
    return request.param


# Create --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model_to_create(models_with_kwargs):
    kw_0, _, _ = models_with_kwargs.kwargs
    return models_with_kwargs.models, kw_0.request, kw_0.blank_opts


@pytest.fixture(scope="session")
def create_with_db():
    def _create_with_db(session, models, request):
        table = models.table(**request)
        commit_to_session(session, table)
        # Need to `get` b/c db doesn't return a response
        model_db = session.get(models.table, table.id)
        data = model_db.dict()
        return data

    return _create_with_db


@pytest.fixture(scope="session")
def create_with_abstraction():
    def _create_with_abstraction(session, models, request):
        table = models.table(**request)
        model_db = abstractions.create(session=session, table_cls=models.table, model=table,)
        data = model_db.dict()
        return data

    return _create_with_abstraction


@pytest.fixture(scope="session")
def create_with_client():
    def _create_with_client(base_url, models, json):
        client = Client(base_url)
        response = client.post(models.path, json)
        response.raise_for_status()
        data = response.json()
        return data

    return _create_with_client


@pytest.fixture(scope="session")
def create_with_cli():
    def _create_with_cli(base_url, models, request):
        data = get_data_from_cli("post", base_url, models.path, request)
        return data

    return _create_with_cli


@pytest.fixture(
    scope="session",
    params=[
        lazy_fixture("create_with_db"),
        lazy_fixture("create_with_abstraction"),
        lazy_fixture("create_with_client"),
        lazy_fixture("create_with_cli"),
    ],
)
def create_func(request):
    return request.param


# Read ----------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def models_to_read(models_with_kwargs):
    models = models_with_kwargs.models
    kw_0, kw_1, _ = models_with_kwargs.kwargs
    model_0 = models.table(**kw_0.request)
    model_1 = models.table(**kw_1.request)
    return models, (model_0, model_1)


@pytest.fixture(scope="session")
def single_model_to_read(models_with_kwargs):
    models = models_with_kwargs.models
    _, _, kw_2 = models_with_kwargs.kwargs
    table = models.table(**kw_2.request)
    return models, table


# Update --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model_to_update(models_with_kwargs):
    models = models_with_kwargs.models
    kw_0, kw_1, _ = models_with_kwargs.kwargs
    table = models.table(**kw_0.request)
    different_kws = copy.deepcopy(kw_1.request)
    key = list(different_kws)[0]
    update_with = {key: different_kws.pop(key)}
    return models, table, update_with


# Delete --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model_to_delete(models_with_kwargs):
    models = models_with_kwargs.models
    kw_0, _, _ = models_with_kwargs.kwargs
    table = models.table(**kw_0.request)
    return models, table
