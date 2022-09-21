from typing import Tuple
from urllib.parse import urlparse

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
    make_dataflow_job_name,
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


@pytest.mark.asyncio
@pytest.mark.parametrize("recipe_run_id", [1, 9999, 10_000, 9_999_999, 10_000_000])
async def test_make_dataflow_job_name(app_hook_config_url, recipe_run_id):
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
        "is_test": True,
        "dataset_type": "zarr",
        "dataset_public_url": None,
        "message": None,
        "id": recipe_run_id,
    }
    recipe_run = MODELS["recipe_run"].table(**recipe_run_kws)
    gh_backend_kws = {
        "_app_hook_config_url": app_hook_config_url,
    }
    gh_backend = _MockGitHubBackend(**gh_backend_kws)
    mock_gh = get_mock_github_session(gh_backend)(http_session)

    def reverse_encoding(job_name: str) -> Tuple[str, int]:
        # TODO: This code is duplicative of the code used in the submodule
        # `dataflow-status-monitoring/src/main.py` to decode job names. Ideally, we should be using
        # the *actual* decoding function to test here, however the submodule code is not currently
        # factored in such a way that makes that possible. (That is, decoding job names is done as
        # part of a monolithic function there. If it were it's own function, we could import it
        # here.) The decode behavior should be definitely be factored into a distinct functions and
        # probably be situated in the same module as the encoder. I'm not yet clear where these
        # paired functions should live, however:
        #   1. Together in `dataflow-status-monitoring`?
        #   2. Together in `pangeo-forge-orchestrator`?
        # I favor the latter, but if we go this route, how does `dataflow-status-monitoring` access
        # the decoder function without a circular dependency? Perhaps this points to just merging
        # `dataflow-status-monitoring` code into `pangeo-forge-orchestrator`.
        job_name = job_name[1:]  # drop leading 'a' from job_name
        as_pairs = [a + b for a, b in zip(job_name[::2], job_name[1::2])]
        control_character_idx = [
            i for i, val in enumerate(as_pairs) if chr(int(val, 16)) == "%"
        ].pop(0)
        recipe_run_id = int("".join(as_pairs[control_character_idx + 1 :]))
        # NOTE: in `dataflow-status-monitoring` this variable is named `webhook_url`, but I realized
        # as a I was writing this test, that it's more accurately named `*_netloc`, rather than `url`
        decoded_netloc = "".join([chr(int(val, 16)) for val in as_pairs[:control_character_idx]])
        return decoded_netloc, recipe_run_id

    app_hook_netloc = urlparse(app_hook_config_url).netloc
    if len(app_hook_netloc) + len(str(recipe_run_id)) > 32:
        # the current encoding scheme requires 2 characters for every 1 character in the decoded
        # content. therefore, if the decoded content exceeds 32 chars in length, then we cannot
        # create a valid dataflow job name (which cannot be > 64 chars) for this content. in
        # practice, with our current DNS names, this means:
        #   1. we cannot have > 9999 recipe_runs in the staging database
        #   2. we cannot have > 9_999_999 recipe_runs in the production database
        # which seems tenable. the greater number of allowable recipe_runs in the prod database
        # is due to the fact that the DNS name for prod API is 8 characters shorter than the DNS
        # name for the staging API, therefore we gain 8 additional characters (i.e. digits) of
        # encodable content length.
        assert recipe_run_id in (10_000, 9_999_999, 10_000_000)

        if app_hook_netloc == "api.pangeo-forge.org":
            assert recipe_run_id > 9_999_999
        elif app_hook_netloc == "api-staging.pangeo-forge.org":
            assert any([recipe_run_id == n for n in (10_000, 9_999_999, 10_000_000)])

        with pytest.raises(ValueError, match=r"exceeds max dataflow job name len of 64 chars.$"):
            _ = await make_dataflow_job_name(recipe_run, mock_gh)

    else:
        job_name = await make_dataflow_job_name(recipe_run, mock_gh)
        decoded_netloc, recipe_run_id = reverse_encoding(job_name)
        assert f"https://{decoded_netloc}/github/hooks/" == app_hook_config_url
        assert recipe_run_id == recipe_run.id


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
