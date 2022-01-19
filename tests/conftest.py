import socket
import subprocess
import time

import pytest
from fastapi.testclient import TestClient
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel, create_engine
from typer.testing import CliRunner

from pangeo_forge_orchestrator.models import MODELS

from .interfaces import CommandLineCRUD, FastAPITestClientCRUD


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
        "pangeo_forge_orchestrator.api:app",
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


def clear_table(session: Session, table_model: SQLModel):
    session.query(table_model).delete()
    session.commit()
    assert len(session.query(table_model).all()) == 0  # make sure the database is empty


@pytest.fixture
def session(uncleared_session):
    with uncleared_session as session:
        for k in MODELS:
            clear_table(session, MODELS[k].table)  # make sure the database is empty
        yield session


@pytest.fixture
def http_server(http_server_url, session):
    for k in MODELS:
        clear_table(session, MODELS[k].table)  # make sure the database is empty
    return http_server_url


@pytest.fixture(scope="session")
def fastapi_test_client_uncleared():
    from pangeo_forge_orchestrator.api import app, get_session

    return TestClient(app), get_session


@pytest.fixture
def fastapi_test_client(fastapi_test_client_uncleared):
    # this might be using a different session (and different database!) from
    # the session we generated above
    test_client, get_session = fastapi_test_client_uncleared
    # this does not feel kosher
    session = next(iter(get_session()))
    for k in MODELS:
        clear_table(session, MODELS[k].table)
    return test_client


@pytest.fixture
def fastapi_test_crud_client(fastapi_test_client):
    return FastAPITestClientCRUD(fastapi_test_client)


@pytest.fixture
def cli_crud_client(http_server_url):
    from pangeo_forge_orchestrator.cli import cli

    runner = CliRunner(env={"PANGEO_FORGE_DATABASE_URL": http_server_url})
    return CommandLineCRUD(cli, runner)


@pytest.fixture(params=[lazy_fixture("fastapi_test_crud_client"), lazy_fixture("cli_crud_client")])
def client(request):
    return request.param
