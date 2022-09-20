import subprocess
from typing import List
from urllib.parse import urlparse

import pytest
import pytest_asyncio

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.routers.github_app import DEFAULT_BACKEND_NETLOC

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session


def mock_subprocess_check_output(cmd: List[str]):
    """ """

    if cmd[0] == "pangeo-forge-runner":
        if cmd[1] == "expand-meta":
            # As a first step, we are not accounting for any arguments passed to expand-meta.
            # This return value was obtained by running, with pangeo-forge-runner==0.3
            #  ```
            #  subprocess.check_output(
            #      "pangeo-forge-runner expand-meta --repo https://github.com/pangeo-forge/github-app-sandbox-repository --ref 0fd9b13f0d718772e78fc2b53fd7e9da82a522f3 --json".split()
            #  )
            #  ```
            return (
                '{"message": "Picked Git content provider.\\n", "status": "fetching"}\n'
                '{"message": "Cloning into \'/var/folders/tt/4f941hdn0zq549zdwhcgg98c0000gn/T/tmp10gezh_p\'...\\n", "status": "fetching"}\n'
                '{"message": "HEAD is now at 0fd9b13 Update foo.txt\\n", "status": "fetching"}\n'
                '{"message": "Expansion complete", "status": "completed", "meta": {"title": "Global Precipitation Climatology Project", "description": "Global Precipitation Climatology Project (GPCP) Daily Version 1.3 gridded, merged ty satellite/gauge precipitation Climate data Record (CDR) from 1996 to present.\\n", "pangeo_forge_version": "0.9.0", "pangeo_notebook_version": "2022.06.02", "recipes": [{"id": "gpcp", "object": "recipe:recipe"}], "provenance": {"providers": [{"name": "NOAA NCEI", "description": "National Oceanographic & Atmospheric Administration National Centers for Environmental Information", "roles": ["host", "licensor"], "url": "https://www.ncei.noaa.gov/products/global-precipitation-climatology-project"}, {"name": "University of Maryland", "description": "University of Maryland College Park Earth System Science Interdisciplinary Center (ESSIC) and Cooperative Institute for Climate and Satellites (CICS).\\n", "roles": ["producer"], "url": "http://gpcp.umd.edu/"}], "license": "No constraints on data access or use."}, "maintainers": [{"name": "Ryan Abernathey", "orcid": "0000-0001-5999-4917", "github": "rabernat"}], "bakery": {"id": "pangeo-ldeo-nsf-earthcube"}}}\n'
            )
        else:
            raise NotImplementedError(f"Command {cmd} not implemented in tests.")
    else:
        raise NotImplementedError(
            f"Command {cmd} does not begin with 'pangeo-forge-runner'. Currently, "
            "'pangeo-forge-runner' is the only command line mock implemented."
        )


@pytest_asyncio.fixture
async def synchronize_request_fixture(
    webhook_secret,
    async_app_client,
    admin_key,
    request,
    staged_recipes_pulls_files,
    app_hook_config_url,
):
    headers = {"X-GitHub-Event": "pull_request"}
    payload = {
        "action": "synchronize",
        "pull_request": {
            "number": 1,
            "base": {
                "repo": {
                    "html_url": f"https://github.com/{request.param}",
                    "url": f"https://api.github.com/repos/{request.param}",
                    "full_name": request.param,
                },
            },
            "head": {
                "repo": {
                    "html_url": "https://github.com/contributor-username/staged-recipes",
                    "url": "https://api.github.com/repos/contributor-username/staged-recipes",
                },
                "sha": "abc",
            },
            "labels": [],
            "title": "Add XYZ awesome dataset",
        },
    }
    request = {"headers": headers, "payload": payload}

    # setup database for this test
    admin_headers = {"X-API-Key": admin_key}
    bakery_create_response = await async_app_client.post(
        "/bakeries/",
        json={  # TODO: set dynamically
            "region": "us-central1",
            "name": "pangeo-ldeo-nsf-earthcube",
            "description": "A great bakery to test with!",
        },
        headers=admin_headers,
    )
    assert bakery_create_response.status_code == 200
    feedstock_create_response = await async_app_client.post(
        "/feedstocks/",
        json={"spec": "pangeo-forge/staged-recipes"},  # TODO: set dynamically
        headers=admin_headers,
    )
    assert feedstock_create_response.status_code == 200

    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_accessible_repos": [
            {"full_name": "pangeo-forge/staged-recipes"},
            {"full_name": "pangeo-forge/pangeo-forge.org"},
        ],
        "_app_hook_config_url": app_hook_config_url,
        "_check_runs": list(),
        "_pulls_files": {
            "pangeo-forge/staged-recipes": staged_recipes_pulls_files,
        },
    }
    expected_recipe_runs_response = [
        {
            "recipe_id": "gpcp",
            "bakery_id": 1,
            "feedstock_id": 1,
            "head_sha": "abc",
            "version": "",
            "started_at": "2022-08-11T21:03:56",
            "completed_at": None,
            "conclusion": None,
            "status": "queued",
            "is_test": True,
            "dataset_type": "zarr",
            "dataset_public_url": None,
            "message": None,
            "id": 1,
        }
    ]
    frontend_url = "https://pangeo-forge.org/dashboard/recipe-run/1?feedstock_id=1"
    if DEFAULT_BACKEND_NETLOC not in app_hook_config_url:
        frontend_url += f"&orchestratorEndpoint={urlparse(app_hook_config_url).netloc}"
    expected_check_runs_response = {
        "total_count": 1,
        "check_runs": [
            {
                "name": "synchronize",
                "head_sha": "abc",
                "status": "completed",
                "started_at": "2022-08-11T21:22:51Z",
                "output": {
                    "title": "Recipe runs queued for latest commit",
                    "summary": f"Recipe runs created at commit `abc`:\n- {frontend_url}",
                },
                "details_url": "https://pangeo-forge.org/",
                "id": 0,
                "conclusion": "success",
                "completed_at": "2022-08-11T21:22:51Z",
            }
        ],
    }

    yield (
        add_hash_signature(request, webhook_secret),
        _MockGitHubBackend(**gh_backend_kws),
        expected_recipe_runs_response,
        expected_check_runs_response,
    )

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "synchronize_request_fixture",
    ["pangeo-forge/staged-recipes", "pangeo-forge/pangeo-forge.org"],
    indirect=True,
)
async def test_receive_synchronize_request(
    mocker,
    async_app_client,
    synchronize_request_fixture,
):
    (
        synchronize_request,
        gh_backend,
        expected_recipe_runs_response,
        expected_check_runs_response,
    ) = synchronize_request_fixture
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )

    mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)
    response = await async_app_client.post(
        "/github/hooks/",
        json=synchronize_request["payload"],
        headers=synchronize_request["headers"],
    )

    if synchronize_request["payload"]["pull_request"]["base"]["repo"]["full_name"].endswith(
        "pangeo-forge.org"
    ):
        assert "Skipping synchronize for repo" in response.json()["message"]
    else:
        assert response.status_code == 202
        # first assert that the recipe runs were created as expected
        recipe_runs_response = await async_app_client.get("/recipe_runs/")
        assert recipe_runs_response.status_code == 200
        for k in expected_recipe_runs_response[0]:
            if k not in ["started_at", "completed_at"]:
                assert expected_recipe_runs_response[0][k] == recipe_runs_response.json()[0][k]

        # then assert that the check runs were created as expected
        commit_sha = recipe_runs_response.json()[0]["head_sha"]
        check_runs_response = await async_app_client.get(
            f"/feedstocks/1/commits/{commit_sha}/check-runs"
        )

        assert expected_check_runs_response["total_count"] == 1
        for k in expected_check_runs_response["check_runs"][0]:
            if k not in ["started_at", "completed_at"]:
                assert (
                    expected_check_runs_response["check_runs"][0][k]
                    == check_runs_response.json()["check_runs"][0][k]
                )
