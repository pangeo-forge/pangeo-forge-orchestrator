import os
import secrets

import pytest
import pytest_asyncio
import yaml  # type: ignore
from asgi_lifespan import LifespanManager
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pytest_lazyfixture import lazy_fixture

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.api import app

from .github_app.fixtures import *  # noqa: F401 F403
from .interfaces import FastAPITestClientCRUD


@pytest.fixture(autouse=True, scope="session")
def setup_and_teardown(
    session_mocker,
    mock_app_config_path,
    mock_secrets_dir,
    mock_bakeries_dir,
):
    def get_mock_app_config_path():
        return mock_app_config_path

    def get_mock_secrets_dir():
        return mock_secrets_dir

    def get_mock_bakeries_dir():
        return mock_bakeries_dir

    session_mocker.patch.object(
        pangeo_forge_orchestrator.config,
        "get_app_config_path",
        get_mock_app_config_path,
    )
    session_mocker.patch.object(
        pangeo_forge_orchestrator.config,
        "get_secrets_dir",
        get_mock_secrets_dir,
    )
    session_mocker.patch.object(
        pangeo_forge_orchestrator.config,
        "get_bakeries_dir",
        get_mock_bakeries_dir,
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
def mock_config_kwargs(webhook_secret, private_key):
    return {
        "github_app": {
            "id": 1234567,
            "app_name": "pytest-mock-github-app",
            "webhook_url": "https://api.pangeo-forge.org/github/hooks",  # TODO: fixturize
            "webhook_secret": webhook_secret,
            "private_key": private_key,
        },
    }


@pytest.fixture(scope="session")
def mock_secrets_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("secrets")


@pytest.fixture(scope="session")
def mock_app_config_path(mock_config_kwargs, mock_secrets_dir):
    """ """
    path = mock_secrets_dir / "config.pytest-deployment.yaml"
    with open(path, "w") as f:
        yaml.dump(mock_config_kwargs, f)

    return path


@pytest.fixture(scope="session")
def mock_bakeries_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("bakeries")


@pytest.fixture(scope="session", autouse=True)
def mock_bakeries_config_paths(mock_bakeries_dir):
    """ """
    path = mock_bakeries_dir / "pangeo-ldeo-nsf-earthcube.pytest-deployment.yaml"
    kws = dict(
        Bake=dict(
            bakery_class="foo",
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
    with open(path, "w") as f:
        yaml.dump(kws, f)

    return [str(path)]  # TODO: test with > 1 bakery


@pytest.fixture(scope="session")
def mock_secret_bakery_args_paths(mock_secrets_dir):
    """ """
    path = mock_secrets_dir / "bakery-args.pangeo-ldeo-nsf-earthcube.yaml"
    kws = dict()  # TODO: actually pass some values
    with open(path, "w") as f:
        yaml.dump(kws, f)

    return [str(path)]  # TODO: test with > 1 bakery env


# For this general pattern, see
# https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html
# which is adjustmented according to https://stackoverflow.com/a/73019163.
# And for LifespanManager, see https://github.com/tiangolo/fastapi/issues/2003#issuecomment-801140731.
@pytest_asyncio.fixture
async def async_app_client():
    async with AsyncClient(app=app, base_url="http://test") as client, LifespanManager(app):
        yield client


# General Fixtures --------------------------------------------------------------------------------


@pytest.fixture
def fastapi_test_crud_client():
    with TestClient(app) as fastapi_test_client:
        yield FastAPITestClientCRUD(fastapi_test_client)


@pytest.fixture(
    params=[
        lazy_fixture("fastapi_test_crud_client"),
    ]
)
def client(request):
    return request.param
