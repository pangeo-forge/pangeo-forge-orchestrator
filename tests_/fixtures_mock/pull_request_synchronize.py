import subprocess
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
import pytest_mock

from pangeo_forge_orchestrator.api import app
from pangeo_forge_orchestrator.routers.github_app import get_http_session

from ..fixture_models import FixturedGitHubEvent
from .helpers import MockHttpResponses, add_hash_signature, make_mock_httpx_client


@pytest_asyncio.fixture(
    params=[
        dict(
            number=1,
            base_repo_full_name="pangeo-forge/staged-recipes",
            title="Add XYZ awesome dataset",
            head_sha="abc",
        ),
    ],
)
async def recipe_pr(
    webhook_secret: str,
    request: pytest.FixtureRequest,
    mocker: pytest_mock.MockerFixture,
    async_app_client: httpx.AsyncClient,
) -> AsyncGenerator[FixturedGitHubEvent, None]:
    fixture_request = request  # disambiguate with a more specific name
    headers = {"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "123-456-789"}
    payload = {
        "action": "synchronize",
        "pull_request": {
            "number": fixture_request.param["number"],
            "base": {
                "repo": {
                    "html_url": f"https://github.com/{fixture_request.param['base_repo_full_name']}",
                    "url": f"https://api.github.com/repos/{fixture_request.param['base_repo_full_name']}",
                    "full_name": fixture_request.param["base_repo_full_name"],
                },
            },
            "head": {
                "repo": {
                    "html_url": "https://github.com/contributor-username/staged-recipes",
                    "url": "https://api.github.com/repos/contributor-username/staged-recipes",
                },
                "sha": fixture_request.param["head_sha"],
            },
            "labels": [],
            "title": fixture_request.param["title"],
        },
    }
    mock_github_webhook = add_hash_signature(
        {"headers": headers, "payload": payload}, webhook_secret
    )

    # setup mock github backend for this test

    mock_github_responses = {
        "/app/installations": MockHttpResponses(
            GET=httpx.Response(200, json=[{"id": 1234567}]),
        ),
        f"/app/installations/{1234567}/access_tokens": MockHttpResponses(
            POST=httpx.Response(200, json={"token": "abcdefghijklmnop"}),
        ),
        "/repos/pangeo-forge/staged-recipes/check-runs": MockHttpResponses(
            POST=httpx.Response(200, json={"id": 1234567890})
        ),
        "/repos/pangeo-forge/staged-recipes/pulls/1/files": MockHttpResponses(
            GET=httpx.Response(
                200,
                json=[
                    {
                        "filename": "recipes/new-dataset/recipe.py",
                        "contents_url": (
                            "https://api.github.com/repos/contributor-username/staged-recipes/"
                            "contents/recipes/new-dataset/recipe.py"
                        ),
                        "sha": "abcdefg",
                    },
                    {
                        "filename": "recipes/new-dataset/meta.yaml",
                        "contents_url": (
                            "https://api.github.com/repos/contributor-username/staged-recipes/"
                            "contents/recipes/new-dataset/meta.yaml"
                        ),
                        "sha": "abcdefg",
                    },
                ],
            )
        ),
        "/repos/pangeo-forge/staged-recipes/check-runs/1234567890": MockHttpResponses(
            PATCH=httpx.Response(200),
        ),
    }

    def get_mock_http_session():
        return make_mock_httpx_client(mock_github_responses)

    # https://fastapi.tiangolo.com/advanced/testing-dependencies/#testing-dependencies-with-overrides
    app.dependency_overrides[get_http_session] = get_mock_http_session

    def mock_subprocess_check_output(cmd: list[str]):
        return (
            '{"message": "Picked Git content provider.\\n", "status": "fetching"}\n'
            '{"message": "Cloning into \'/var/folders/tt/4f941hdn0zq549zdwhcgg98c0000gn/T/tmp10gezh_p\'...\\n", "status": "fetching"}\n'
            '{"message": "HEAD is now at 0fd9b13 Update foo.txt\\n", "status": "fetching"}\n'
            '{"message": "Expansion complete", "status": "completed", "meta": {"title": "Global Precipitation Climatology Project", "description": "Global Precipitation Climatology Project (GPCP) Daily Version 1.3 gridded, merged ty satellite/gauge precipitation Climate data Record (CDR) from 1996 to present.\\n", "pangeo_forge_version": "0.9.0", "pangeo_notebook_version": "2022.06.02", "recipes": [{"id": "gpcp", "object": "recipe:recipe"}], "provenance": {"providers": [{"name": "NOAA NCEI", "description": "National Oceanographic & Atmospheric Administration National Centers for Environmental Information", "roles": ["host", "licensor"], "url": "https://www.ncei.noaa.gov/products/global-precipitation-climatology-project"}, {"name": "University of Maryland", "description": "University of Maryland College Park Earth System Science Interdisciplinary Center (ESSIC) and Cooperative Institute for Climate and Satellites (CICS).\\n", "roles": ["producer"], "url": "http://gpcp.umd.edu/"}], "license": "No constraints on data access or use."}, "maintainers": [{"name": "Ryan Abernathey", "orcid": "0000-0001-5999-4917", "github": "rabernat"}], "bakery": {"id": "pangeo-ldeo-nsf-earthcube"}}}\n'
        )

    mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)

    # there are two layers of github mocking: one for the routes accessed by the app itself (above).
    # and another for routes that the tests need to access to make assertions against, here:
    mock_gh_responses_for_pytest = {
        (
            f"/repos/{fixture_request.param['base_repo_full_name']}"
            f"/commits/{fixture_request.param['head_sha']}/check-runs"
        ): MockHttpResponses(
            GET=httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "check_runs": [
                        {
                            "name": "Parse meta.yaml",
                            "head_sha": fixture_request.param["head_sha"],
                            "status": "completed",
                            "started_at": "2022-08-11T21:22:51Z",
                            "output": {
                                "title": "Recipe runs queued for latest commit",
                                "summary": "",
                            },
                            "details_url": "https://pangeo-forge.org/",
                            "id": 0,
                            "conclusion": "success",
                            "completed_at": "2022-08-11T21:22:51Z",
                        }
                    ],
                },
            )
        ),
    }

    yield FixturedGitHubEvent(
        app_client=async_app_client,
        github_webhook=mock_github_webhook,
        pytest_http_client=make_mock_httpx_client(mock_gh_responses_for_pytest),
    )

    # cleanup overrides set above
    app.dependency_overrides = {}
    assert not app.dependency_overrides
