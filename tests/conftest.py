import os
import signal
import socket
import subprocess
import time

import pytest
from fastapi.testclient import TestClient
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel
from typer.testing import CliRunner

try:
    _ = os.environ["DATABASE_URL"]
except KeyError:  # pragma: no cover
    raise ValueError(
        "The DATABASE_URL environment variable must be set. If the "
        "corresponding database is Postgres, it must be migrated in order "
        "to run the tests. See README.md for details."
    )

from pangeo_forge_orchestrator.models import MODELS

from .interfaces import CommandLineCRUD, FastAPITestClientCRUD


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


# General fixtures ------------------------------------------------------------------------


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
    from pangeo_forge_orchestrator.api import get_session

    uncleared_session = next(iter(get_session()))  # this does not feel kosher

    with uncleared_session as session:
        for k in MODELS:
            clear_table(session, MODELS[k].table)  # make sure the database is empty
        yield session


@pytest.fixture
def fastapi_test_crud_client(session):  # pass `session` so that `clear_table` is called
    from pangeo_forge_orchestrator.api import app

    with TestClient(app) as client:
        yield FastAPITestClientCRUD(client)


@pytest.fixture
def cli_crud_client(http_server_url, session):  # pass `session` so that `clear_table` is called
    from pangeo_forge_orchestrator.cli import cli

    runner = CliRunner(env={"PANGEO_FORGE_DATABASE_URL": http_server_url})
    return CommandLineCRUD(cli, runner)


# TODO: Figure out why `cli_crud_client` has to be the first item in the `params` list (this appears
# necessary to ensure that the SQLite database is properly initialized from `on_startup` function in
# `pangeo_forge_orchestrator.api`)
@pytest.fixture(params=[lazy_fixture("cli_crud_client"), lazy_fixture("fastapi_test_crud_client")])
def client(request):
    return request.param
