import jwt
import pytest
from gidgethub.aiohttp import GitHubAPI

from pangeo_forge_orchestrator.http import http_session
from pangeo_forge_orchestrator.routers.github_app import (
    get_access_token,
    get_app_webhook_url,
    get_github_session,
    get_jwt,
    get_repo_id,
    html_to_api_url,
    html_url_to_repo_full_name,
    list_accessible_repos,
)

from .fixtures import _MockGitHubBackend, get_mock_github_session


def test_get_jwt(rsa_key_pair):
    _, public_key = rsa_key_pair
    encoded_jwt = get_jwt()
    decoded = jwt.decode(encoded_jwt, public_key, algorithms=["RS256"])
    assert list(decoded.keys()) == ["iat", "exp", "iss"]
    assert all([isinstance(v, int) for v in decoded.values()])


def test_get_github_session():
    gh = get_github_session(http_session)
    assert isinstance(gh, GitHubAPI)


@pytest.mark.asyncio
async def test_get_access_token():
    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
    }
    gh_backend = _MockGitHubBackend(**gh_backend_kws)
    mock_gh = get_mock_github_session(gh_backend)(http_session)
    token = await get_access_token(mock_gh)
    assert token.startswith("ghs_")
    assert len(token) == 40  # "ghs_" (4 chars) + 36 character token


@pytest.mark.asyncio
async def test_get_app_webhook_url(app_hook_config_url):
    gh_backend_kws = {
        "_app_hook_config_url": app_hook_config_url,
    }
    gh_backend = _MockGitHubBackend(**gh_backend_kws)
    mock_gh = get_mock_github_session(gh_backend)(http_session)
    url = await get_app_webhook_url(mock_gh)
    assert url == app_hook_config_url


@pytest.mark.parametrize("repo_full_name", ["pangeo-forge/staged-recipes"])
@pytest.mark.asyncio
async def test_get_repo_id(repo_full_name):
    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_repositories": {repo_full_name: {"id": 987654321}},
    }
    gh_backend = _MockGitHubBackend(**gh_backend_kws)
    mock_gh = get_mock_github_session(gh_backend)(http_session)
    repo_id = await get_repo_id(repo_full_name, mock_gh)
    assert isinstance(repo_id, int)


@pytest.mark.asyncio
async def test_list_accessible_repos():
    accessible_repos = [
        {"full_name": "pangeo-forge/staged-recipes"},
    ]
    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_accessible_repos": accessible_repos,
    }
    gh_backend = _MockGitHubBackend(**gh_backend_kws)
    mock_gh = get_mock_github_session(gh_backend)(http_session)
    repos = await list_accessible_repos(mock_gh)
    assert repos == [r["full_name"] for r in accessible_repos]


# TODO: the functions tested by the next two tests should be removed.
# best practice is to not parse this information from payloads, but rather to extract the
# relevant objects directly from other fields in the payload.


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
