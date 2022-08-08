import os
from dataclasses import dataclass
from typing import List, Optional

import jwt
import pytest
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.http import HttpSession, http_session
from pangeo_forge_orchestrator.routers.github_app import (
    create_check_run,
    get_access_token,
    get_app_webhook_url,
    get_jwt,
    get_repo_id,
    html_to_api_url,
    html_url_to_repo_full_name,
    list_accessible_repos,
    update_check_run,
)


@pytest.fixture
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


@dataclass
class _MockGitHubBackend:
    app_hook_config_url: str
    accessible_repos: List[dict]


@dataclass
class MockGitHubAPI(_MockGitHubBackend):
    http_session: HttpSession
    username: str

    async def getitem(
        self,
        path: str,
        accept: str,
        jwt: Optional[str] = None,
        oauth_token: Optional[str] = None,
    ) -> dict:
        if path == "/app/hook/config":
            return {"url": self.app_hook_config_url}
        elif path.startswith("/repos/"):
            return {"id": 123456789}  # TODO: assign dynamically from _MockGitHubBackend
        elif path == "/installation/repositories":
            return {"repositories": self.accessible_repos}
        else:
            raise NotImplementedError(f"Path '{path}' not supported.")

    async def post(self, path: str, oauth_token: str, accept: str, data: dict):
        return {"id": 1}  # TODO: set `id` dynamically

    async def patch(self, path: str, oauth_token: str, accept: str, data: dict):
        return {}  # TODO: return something


@pytest.fixture
def api_url():
    """In production, this might be configured to point to a different url, for example for
    testing new features on a review deployment."""

    return "https://api.pangeo-forge.org"


@pytest.fixture
def app_hook_config_url(api_url):
    return f"{api_url}/github/hooks/"


@pytest.fixture
def accessible_repos():
    """The repositories in which the app has been installed."""

    return [{"full_name": "pangeo-forge/staged-recipes"}]


@pytest.fixture
def get_mock_github_session(app_hook_config_url, accessible_repos):
    def _get_mock_github_session(http_session: HttpSession):
        backend_kws = {
            "app_hook_config_url": app_hook_config_url,
            "accessible_repos": accessible_repos,
        }
        return MockGitHubAPI(http_session=http_session, username="pangeo-forge", **backend_kws)

    return _get_mock_github_session


def test_get_github_session(mocker, get_mock_github_session):
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    from pangeo_forge_orchestrator.routers.github_app import get_github_session

    gh = get_github_session(http_session)
    assert isinstance(gh, MockGitHubAPI)


@pytest.mark.parametrize(
    "html_url,expected_api_url",
    (
        [
            "https://github.com/pangeo-forge/staged-recipes",
            "https://api.github.com/repos/pangeo-forge/staged-recipes",
        ],
    ),
)
def test_html_to_api_url(html_url, expected_api_url):
    actual_api_url = html_to_api_url(html_url)
    assert actual_api_url == expected_api_url


@pytest.mark.parametrize(
    "html_url,expected_repo_full_name",
    (["https://github.com/pangeo-forge/staged-recipes", "pangeo-forge/staged-recipes"],),
)
def test_html_url_to_repo_full_name(html_url, expected_repo_full_name):
    actual_repo_full_name = html_url_to_repo_full_name(html_url)
    assert actual_repo_full_name == expected_repo_full_name


def test_get_jwt(rsa_key_pair):
    private_key, public_key = rsa_key_pair
    os.environ["PEM_FILE"] = private_key
    encoded_jwt = get_jwt()
    decoded = jwt.decode(encoded_jwt, public_key, algorithms=["RS256"])
    assert list(decoded.keys()) == ["iat", "exp", "iss"]
    assert all([isinstance(v, int) for v in decoded.values()])


@pytest.fixture
def mock_access_token():
    # return value copied from example given here:
    # https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app
    return "ghs_16C7e42F292c6912E7710c838347Ae178B4a"


@pytest.fixture
def get_mock_installation_access_token(mock_access_token):
    async def _get_mock_installation_access_token(
        gh: MockGitHubAPI,
        installation_id: int,
        app_id: int,
        private_key: str,
    ):
        # Set this in the function body (rather than as a default) so it's evaluated at call time,
        # not during fixture collection.
        private_key = os.environ["PEM_FILE"]
        # Our mock function does not actually use the private key, but the real function requires
        # it, so we check here that it exists in the test session, to enhance realism.
        assert private_key is not None
        assert private_key.startswith("-----BEGIN PRIVATE KEY-----")

        return {"token": mock_access_token}

    return _get_mock_installation_access_token


@pytest.mark.asyncio
async def test_get_access_token(
    mocker,
    rsa_key_pair,
    get_mock_github_session,
    get_mock_installation_access_token,
    mock_access_token,
):
    private_key, _ = rsa_key_pair
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_installation_access_token",
        get_mock_installation_access_token,
    )
    token = await get_access_token(mock_gh)
    assert token == mock_access_token


@pytest.mark.asyncio
async def test_get_app_webhook_url(rsa_key_pair, get_mock_github_session):
    private_key, _ = rsa_key_pair
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    url = await get_app_webhook_url(mock_gh)
    assert url == "https://api.pangeo-forge.org/github/hooks/"


@pytest.mark.asyncio
async def test_create_check_run(
    mocker,
    rsa_key_pair,
    get_mock_github_session,
    get_mock_installation_access_token,
    api_url,
):
    private_key, _ = rsa_key_pair
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_installation_access_token",
        get_mock_installation_access_token,
    )
    data = dict()
    response = await create_check_run(mock_gh, api_url, data)
    assert isinstance(response["id"], int)


@pytest.mark.asyncio
async def test_update_check_run(
    mocker,
    rsa_key_pair,
    get_mock_github_session,
    get_mock_installation_access_token,
    api_url,
):
    private_key, _ = rsa_key_pair
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_installation_access_token",
        get_mock_installation_access_token,
    )
    data = dict()
    _ = await update_check_run(mock_gh, api_url, 1, data)
    # TODO: assert something here. currently, just a smoke test.


@pytest.mark.parametrize("repo_full_name", ["pangeo-forge/staged-recipes"])
@pytest.mark.asyncio
async def test_get_repo_id(
    mocker,
    rsa_key_pair,
    get_mock_github_session,
    get_mock_installation_access_token,
    repo_full_name,
):
    private_key, _ = rsa_key_pair
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_installation_access_token",
        get_mock_installation_access_token,
    )
    repo_id = await get_repo_id(repo_full_name, mock_gh)
    assert isinstance(repo_id, int)


@pytest.mark.asyncio
async def test_list_accessible_repos(
    mocker,
    rsa_key_pair,
    get_mock_github_session,
    get_mock_installation_access_token,
    accessible_repos,
):
    private_key, _ = rsa_key_pair
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_installation_access_token",
        get_mock_installation_access_token,
    )
    repos = await list_accessible_repos(mock_gh)
    assert repos == [r["full_name"] for r in accessible_repos]


# @pytest.mark.anyio
# async def test_root():
#    async with AsyncClient(app=app, base_url="http://test") as ac:
#        response = await ac.get("/")
#    assert response.status_code == 200
#    assert response.json() == {"message": "Tomato"}
