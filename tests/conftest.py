import hashlib
import os
import signal
import socket
import subprocess
import time
import uuid
from unittest import mock

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel
from typer.testing import CliRunner

from pangeo_forge_orchestrator.api import app
from pangeo_forge_orchestrator.models import MODELS

from .interfaces import CommandLineCRUD, FastAPITestClientCRUD


# For this general pattern, see
# https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html
# which is adjustmented according to https://stackoverflow.com/a/73019163.
# And for LifespanManager, see https://github.com/tiangolo/fastapi/issues/2003#issuecomment-801140731.
@pytest_asyncio.fixture
async def async_app_client():
    async with AsyncClient(app=app, base_url="http://test") as client, LifespanManager(app):
        yield client


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


def clear_table(session: Session, table_model: SQLModel):
    session.query(table_model).delete()
    if session.connection().engine.url.drivername == "postgresql":
        # if testing against persistent local postgres server, reset primary keys
        cmd = f"ALTER SEQUENCE {table_model.__name__}_id_seq RESTART WITH 1"
        session.exec(cmd)
    session.commit()
    assert len(session.query(table_model).all()) == 0  # make sure the database is empty


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
def http_server_url():
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

    time.sleep(2)  # let the server start up

    yield url

    os.killpg(os.getpgid(p.pid), signal.SIGTERM)


@pytest.fixture
def session():
    from pangeo_forge_orchestrator.database import engine

    with Session(engine) as session:
        for k in MODELS:
            clear_table(session, MODELS[k].table)  # make sure the database is empty
        yield session


@pytest.fixture
def http_server(http_server_url, session):
    for k in MODELS:
        clear_table(session, MODELS[k].table)
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
def cli_crud_client(http_server_url, session):  # pass `session` so that `clear_table` is called
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
        # Note: the CLI fixtures need to be first because they will trigger
        # the db to be initialized; otherwise the `session` fixture will
        # fail because it can't delete a non-existent table.
        # This feels fragile. Should be fixed by refactoring the fixtures.
        lazy_fixture("cli_crud_client"),
        lazy_fixture("cli_crud_client_authorized"),
        lazy_fixture("fastapi_test_crud_client"),
        lazy_fixture("fastapi_test_crud_client_authorized"),
    ]
)
def client(request):
    return request.param
