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

Hero = MODELS["hero"].table  # TODO: remove once refactor is complete

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


# Create --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def create_hero_request():
    endpoint = "/heroes/"
    request = {"name": "Deadpond", "secret_name": "Dive Wilson"}
    blank_opts = ["age"]
    return endpoint, request, blank_opts


@pytest.fixture(
    scope="session", params=[lazy_fixture("create_hero_request")],
)
def create_request(request):
    return request.param


# Read ----------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def heroes_to_read(scope="session"):
    endpoint = "/heroes/"
    hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
    hero_2 = Hero(name="Rusty-Man", secret_name="Tommy Sharp", age=48)
    return endpoint, (hero_1, hero_2)


@pytest.fixture(
    scope="session", params=[lazy_fixture("heroes_to_read")],
)
def models_to_read(request):
    return request.param


@pytest.fixture(scope="session")
def single_hero_to_read(scope="session"):
    endpoint = "/heroes/"
    hero_1 = Hero(name="Loner Hero", secret_name="Hidden Loner")
    return endpoint, hero_1


@pytest.fixture(
    scope="session", params=[lazy_fixture("single_hero_to_read")],
)
def single_model_to_read(request):
    return request.param
