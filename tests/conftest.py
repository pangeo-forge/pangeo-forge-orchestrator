import hashlib
import os
import signal
import socket
import subprocess
import time
import uuid
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel, create_engine
from typer.testing import CliRunner

from pangeo_forge_orchestrator.api import app
from pangeo_forge_orchestrator.database import get_database_url_from_env
from pangeo_forge_orchestrator.models import MODELS

from .interfaces import CommandLineCRUD, FastAPITestClientCRUD

DATABASE_URL = get_database_url_from_env()


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


# General fixtures ------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_keys():
    salt = uuid.uuid4().hex
    raw_key = uuid.uuid4().hex
    encrypted_key = hashlib.sha256(salt.encode() + raw_key.encode()).hexdigest()
    return salt, raw_key, encrypted_key


@pytest.fixture(autouse=True)
def required_backend_env_vars(api_keys):
    salt, _, encrypted_key = api_keys
    with mock.patch.dict(
        os.environ, {"ENCRYPTION_SALT": salt, "ADMIN_API_KEY_SHA256": encrypted_key}
    ):
        yield


@pytest.fixture(scope="session")
def admin_key(api_keys):
    _, raw_key, _ = api_keys
    return raw_key


@pytest.fixture(scope="session")
def http_server_url(request):
    env_port = os.environ.get("PORT", False)
    port = env_port or get_open_port()
    host = "127.0.0.1"
    url = f"http://{host}:{port}"
    command_list = [
        "gunicorn",
        f"--bind={host}:{port}",
        "--workers=1",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "pangeo_forge_orchestrator.api:app",
        "--log-level=info",
    ]

    # the setsid allows us to properly clean up the gunicorn child processes
    # otherwise those get zombied
    # https://stackoverflow.com/a/22582602/3266235
    p = subprocess.Popen(command_list, preexec_fn=os.setsid)

    time.sleep(1)  # let the server start up

    yield url

    os.killpg(os.getpgid(p.pid), signal.SIGTERM)


@pytest.fixture
def uncleared_session():
    sqlite_file_path = DATABASE_URL
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


# the next two fixtures use the session fixture to clear the database


@pytest.fixture
def fastapi_test_crud_client(session):
    with TestClient(app) as fastapi_test_client:
        yield FastAPITestClientCRUD(fastapi_test_client)


@pytest.fixture
def fastapi_test_crud_client_authorized(session, admin_key):
    with TestClient(app) as fastapi_test_client:
        return FastAPITestClientCRUD(fastapi_test_client, api_key=admin_key)


# alias
authorized_client = fastapi_test_crud_client_authorized


@pytest.fixture
def cli_crud_client(http_server_url):
    from pangeo_forge_orchestrator.cli import cli

    runner = CliRunner(env={"PANGEO_FORGE_SERVER": http_server_url})
    return CommandLineCRUD(cli, runner)


@pytest.fixture
def cli_crud_client_authorized(http_server_url, admin_key):
    from pangeo_forge_orchestrator.cli import cli

    runner = CliRunner(
        env={"PANGEO_FORGE_SERVER": http_server_url, "PANGEO_FORGE_API_KEY": admin_key}
    )
    return CommandLineCRUD(cli, runner)


@pytest.fixture(
    params=[
        lazy_fixture("fastapi_test_crud_client"),
        lazy_fixture("fastapi_test_crud_client_authorized"),
        lazy_fixture("cli_crud_client"),
        lazy_fixture("cli_crud_client_authorized"),
    ]
)
def client(request):
    return request.param
