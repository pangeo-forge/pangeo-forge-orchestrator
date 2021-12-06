import copy
import socket
import subprocess
import time

import pytest
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, create_engine

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
def model_to_create(models_with_kwargs):
    models, kw_0, _, _ = models_with_kwargs
    request = kw_0[0]
    blank_opts = kw_0[1]
    return models, request, blank_opts


# Read ----------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def models_to_read(models_with_kwargs):
    models, kw_0, kw_1, _ = models_with_kwargs
    model_0 = models.table(**kw_0[0])
    model_1 = models.table(**kw_1[0])
    return models, (model_0, model_1)


@pytest.fixture(scope="session")
def single_model_to_read(models_with_kwargs):
    models, _, _, kw_2 = models_with_kwargs
    table = models.table(**kw_2[0])
    return models, table


# Update --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model_to_update(models_with_kwargs):
    models, kw_0, kw_1, _ = models_with_kwargs
    table = models.table(**kw_0[0])
    different_kws = copy.deepcopy(kw_1[0])
    key = list(different_kws)[0]
    update_with = {key: different_kws.pop(key)}
    return models, table, update_with


# Delete --------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def model_to_delete(models_with_kwargs):
    models, kw_0, _, _ = models_with_kwargs
    table = models.table(**kw_0[0])
    return models, table
