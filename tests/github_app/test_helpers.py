import jwt
import pytest
from gidgethub.aiohttp import GitHubAPI

from pangeo_forge_orchestrator.config import get_config
from pangeo_forge_orchestrator.http import http_session
from pangeo_forge_orchestrator.models import MODELS
from pangeo_forge_orchestrator.routers.github_app import (
    get_access_token,
    get_app_webhook_url,
    get_github_session,
    get_jwt,
    get_repo_id,
    get_storage_subpath_identifier,
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


@pytest.mark.parametrize("is_test", [True, False])
@pytest.mark.parametrize("dataset_type", ["zarr"])
@pytest.mark.parametrize("feedstock_spec", ["pangeo-forge/staged-recipes"])
def test_get_storage_subpath_identifier(is_test, dataset_type, feedstock_spec):
    recipe_run_kws = {
        "recipe_id": "liveocean",
        "bakery_id": 1,
        "feedstock_id": 1,
        "head_sha": "35d889f7c89e9f0d72353a0649ed1cd8da04826b",
        "version": "",
        "started_at": "2022-09-19T16:31:43",
        "completed_at": None,
        "conclusion": None,
        "status": "in_progress",
        "is_test": is_test,
        "dataset_type": dataset_type,
        "dataset_public_url": None,
        "message": None,
        "id": 1,
    }
    recipe_run = MODELS["recipe_run"].table(**recipe_run_kws)
    subpath = get_storage_subpath_identifier(feedstock_spec, recipe_run)

    gh_app_name = get_config().github_app.app_name

    prefix = f"{gh_app_name}/"
    suffix = f"{recipe_run_kws['recipe_id']}.{dataset_type}"
    if is_test:
        prefix += "test/"
        suffix = f"recipe-run-{recipe_run.id}/{suffix}"

    assert subpath.startswith(prefix)
    assert subpath.replace(prefix, "").startswith(feedstock_spec)
    assert subpath.endswith(suffix)


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
