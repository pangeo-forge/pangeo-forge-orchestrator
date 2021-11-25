import copy
import socket
import subprocess
import time

import pytest
from fastapi.testclient import TestClient
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from pangeo_forge_orchestrator.api import api, get_session
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


# General ---------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def http_server(tmp_path_factory, request):
    tempdir = tmp_path_factory.mktemp("test-database")
    url = start_http_server(tempdir, request=request)
    return url


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    api.dependency_overrides[get_session] = get_session_override
    client = TestClient(api)
    yield client
    api.dependency_overrides.clear()


# Models --------------------------------------------------------------------------------
# To test additional models, add a session-scoped fixture here which returns a 4-tuple consisting
# of the MultipleModel object followed by three kwargs 2-tuples, each of which starts with a dict
# of kwargs for instantiating the table model, and is followed by either a list of `blank_opts`,
# i.e. optional table fields left out of the kwargs, or `None`.


@pytest.fixture(scope="session")
def hero_with_kwargs():
    return (
        MODELS["hero"],
        (dict(name="Deadpond", secret_name="Dive Wilson"), ["age"]),
        (dict(name="Rusty-Man", secret_name="Tommy Sharp", age=48), None),
        (dict(name="Loner Hero", secret_name="Hidden Loner"), ["age"]),
    )


@pytest.fixture(
    scope="session", params=[lazy_fixture("hero_with_kwargs")],
)
def models_with_kwargs(request):
    return request.param


# Create --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def create_request(models_with_kwargs):
    model, kw_0, _, _ = models_with_kwargs
    endpoint = model.path
    request = kw_0[0]
    blank_opts = kw_0[1]
    return endpoint, request, blank_opts


# Read ----------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def models_to_read(models_with_kwargs):
    models, kw_0, kw_1, _ = models_with_kwargs
    endpoint = models.path
    model_0 = models.table(**kw_0[0])
    model_1 = models.table(**kw_1[0])
    return endpoint, (model_0, model_1)


@pytest.fixture(scope="session")
def single_model_to_read(models_with_kwargs):
    models, _, _, kw_2 = models_with_kwargs
    endpoint = models.path
    model = models.table(**kw_2[0])
    return endpoint, model


# Update --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model_to_update(models_with_kwargs):
    models, kw_0, kw_2, _ = models_with_kwargs
    endpoint = models.path
    model = models.table(**kw_0[0])
    different_kws = copy.deepcopy(kw_2[0])
    key = list(different_kws)[0]
    update_with = {key: different_kws.pop(key)}
    return endpoint, model, update_with


# Delete --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model_to_delete(models_with_kwargs):
    models, kw_0, _, _ = models_with_kwargs
    endpoint = models.path
    model = models.table(**kw_0[0])
    return models, endpoint, model
