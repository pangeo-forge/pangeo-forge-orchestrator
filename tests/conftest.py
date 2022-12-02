import os
import secrets
import uuid

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.api import app
from pangeo_forge_orchestrator.configurables.deployment import _GetDeployment
from pangeo_forge_orchestrator.database import maybe_create_db_and_tables
from pangeo_forge_orchestrator.models import MODELS

from .github_app.fixtures import *  # noqa: F401 F403
from .interfaces import FastAPITestClientCRUD


@pytest.fixture(autouse=True, scope="session")
def setup_and_teardown(
    session_mocker,
    mock_config_path,
):
    # (1) database test session setup
    db_path = os.environ["DATABASE_URL"]
    if db_path.startswith("sqlite") and os.path.exists(db_path.replace("sqlite:///", "")):
        raise ValueError(
            f"Preexisting `{db_path}` may cause test failures. Please remove this file "
            "then restart test session."
        )
    # TODO: remove this call to `maybe_create_db_and_tables`. This function is called on app
    # start-up, so we really shouldn't need to call it manually. However, given how we are handling
    # keeping the tables empty via the ``session`` fixture below, if we do not call this function
    # here, there will not be a ``database.sqlite`` file available when ``session`` is collected.
    # A forthcoming refactor of the test fixtures can resolve this, but for now it's okay to have
    # this called twice (once now and once at app start-up), because it should be idempotent.
    maybe_create_db_and_tables()

    # (2) github app test session setup

    class _GetMockDeployment(_GetDeployment):
        # In a real runtime, this config path will have been set at the command line on startup.
        # In the mock context, we inject it here, to facilitate unit testing, for which the
        # global config won't have been set, because there won't have been a startup event.
        config_file = [mock_config_path]

    session_mocker.patch.object(
        pangeo_forge_orchestrator.configurables.deployment,
        "_GetDeployment",
        _GetMockDeployment,
    )

    session_mocker.patch.dict(
        os.environ,
        {"PANGEO_FORGE_DEPLOYMENT": "pytest-deployment"},
    )
    yield
    # teardown here (none for now)


# GitHub App Fixtures -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rsa_key_pair():
    """Simulates keys generated for the GitHub App. See https://stackoverflow.com/a/39126754."""

    key = rsa.generate_private_key(
        backend=crypto_default_backend(), public_exponent=65537, key_size=2048
    )
    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.PKCS8,
        crypto_serialization.NoEncryption(),
    )
    public_key = key.public_key().public_bytes(
        crypto_serialization.Encoding.OpenSSH, crypto_serialization.PublicFormat.OpenSSH
    )
    return [k.decode(encoding="utf-8") for k in (private_key, public_key)]


@pytest.fixture(scope="session")
def private_key(rsa_key_pair):
    """Convenience fixture so we don't have to unpack ``rsa_key_pair`` in every test function."""

    private_key, _ = rsa_key_pair
    return private_key


@pytest.fixture(scope="session")
def webhook_secret():
    return secrets.token_hex(20)


@pytest.fixture(scope="session")
def mock_config_content(webhook_secret, private_key, api_key):

    fastapi = {"PANGEO_FORGE_API_KEY": api_key}
    github_app = {
        "id": 1234567,
        "app_name": "pytest-mock-github-app",
        "webhook_url": "https://api.pangeo-forge.org/github/hooks",  # TODO: fixturize
        "webhook_secret": webhook_secret,
        "private_key": private_key,
    }
    runner_configs = {
        "pangeo-ldeo-nsf-earthcube": dict(
            Bake=dict(
                bakery_class="foo",
                container_image="gcr.io/pangeo-forge-4967/pangeo/forge:abcdefg",
            ),
            TargetStorage=dict(
                fsspec_class="bar",
                fsspec_args={},
                root_path="baz",
                public_url="https://public-endpoint.org/bucket-name/",
            ),
            InputCacheStorage=dict(
                fsspec_class="bar",
                fsspec_args={},
                root_path="baz",
            ),
            MetadataCacheStorage=dict(
                fsspec_class="bar",
                fsspec_args={},
                root_path="baz",
            ),
        )
    }

    return f"""\
# pytest_deployment.py
c.Deployment.name = "pangeo-forge"
c.GitHubApp.app_name = '{github_app['app_name']}'
c.GitHubApp.id = {github_app['id']}
c.GitHubApp.private_key = '''{github_app['private_key']}'''
c.GitHubApp.webhook_secret = '{github_app['webhook_secret']}'
c.Deployment.fastapi = {fastapi}
c.Deployment.registered_runner_configs = {runner_configs}
"""


@pytest.fixture(scope="session")
def mock_config_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("config")


@pytest.fixture(scope="session")
def mock_config_path(mock_config_content, mock_config_dir) -> str:
    path = mock_config_dir / "pytest_deployment.py"
    with open(path, "w") as f:
        f.write(mock_config_content)
    return str(path)


# For this general pattern, see
# https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html
# which is adjustmented according to https://stackoverflow.com/a/73019163.
# And for LifespanManager, see https://github.com/tiangolo/fastapi/issues/2003#issuecomment-801140731.
@pytest_asyncio.fixture
async def async_app_client():
    async with AsyncClient(app=app, base_url="http://test") as client, LifespanManager(app):
        yield client


# General Fixtures --------------------------------------------------------------------------------


def clear_table(session: Session, table_model: SQLModel):
    session.query(table_model).delete()
    if session.connection().engine.url.drivername == "postgresql":
        # if testing against persistent local postgres server, reset primary keys
        cmd = f"ALTER SEQUENCE {table_model.__name__}_id_seq RESTART WITH 1"
        session.exec(cmd)
    session.commit()
    assert len(session.query(table_model).all()) == 0  # make sure the database is empty


def clear_database():
    # note this function is redundant with the `session` fixture below
    # the difference is that this called explictly by the newer fixtures in `test_github_app`
    # whereas the `session` fixture is called implicitly for the older fixtues used by `test_api`
    # eventually, we should replace the older implict `session` with this more explicit approach
    # for all tests. in the short term, to avoid breaking the older tests, we'll keep this as two
    # separate approaches.
    from pangeo_forge_orchestrator.database import engine

    with Session(engine) as session:
        for k in MODELS:
            clear_table(session, MODELS[k].table)  # make sure the database is empty


@pytest.fixture(scope="session")
def api_key():
    return uuid.uuid4().hex


@pytest.fixture
def session():
    from pangeo_forge_orchestrator.database import engine

    with Session(engine) as session:
        for k in MODELS:
            clear_table(session, MODELS[k].table)  # make sure the database is empty


# the next two fixtures use the session fixture to clear the database


@pytest.fixture
def fastapi_test_crud_client(session):
    with TestClient(app) as fastapi_test_client:
        yield FastAPITestClientCRUD(fastapi_test_client)


@pytest.fixture
def fastapi_test_crud_client_authorized(session, api_key):
    with TestClient(app) as fastapi_test_client:
        return FastAPITestClientCRUD(fastapi_test_client, api_key=api_key)


# alias
authorized_client = fastapi_test_crud_client_authorized


@pytest.fixture(
    params=[
        lazy_fixture("fastapi_test_crud_client"),
        lazy_fixture("fastapi_test_crud_client_authorized"),
    ]
)
def client(request):
    return request.param
