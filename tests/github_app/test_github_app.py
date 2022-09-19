import hashlib
import hmac
import json
import os
import subprocess
from datetime import datetime
from typing import List

import pytest
import pytest_asyncio

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.http import http_session

from ..conftest import clear_database


@pytest.mark.asyncio
async def test_get_deliveries(
    mocker,
    private_key,
    get_mock_github_session,
    app_hook_deliveries,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    response = await async_app_client.get("/github/hooks/deliveries")
    assert response.status_code == 200
    assert response.json() == app_hook_deliveries


@pytest.mark.asyncio
async def test_get_delivery(
    mocker,
    private_key,
    get_mock_github_session,
    app_hook_deliveries,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    for delivery in app_hook_deliveries:
        id_ = delivery["id"]
        response = await async_app_client.get(f"/github/hooks/deliveries/{id_}")
        assert response.status_code == 200
        assert response.json() == delivery


@pytest_asyncio.fixture
async def check_run_create_kwargs(admin_key, async_app_client):
    # setup database
    admin_headers = {"X-API-Key": admin_key}
    fstock_response = await async_app_client.post(
        "/feedstocks/",
        json={"spec": "pangeo-forge/staged-recipes"},  # TODO: set dynamically
        headers=admin_headers,
    )
    assert fstock_response.status_code == 200

    yield dict(
        name="synchronize",
        head_sha="abcdefg",  # TODO: fixturize
        status="in_progress",
        started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        output=dict(
            title="Syncing latest commit to Pangeo Forge Cloud",
            summary="",  # required
        ),
        details_url="https://pangeo-forge.org/",  # TODO: make this more specific.
    )

    # database teardown
    clear_database()


@pytest.mark.asyncio
async def test_get_feedstock_check_runs(
    mocker,
    private_key,
    get_mock_github_session,
    check_run_create_kwargs,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )

    # populate mock github backend with check runs for the feedstock (only 1 for now)
    mock_gh = get_mock_github_session(http_session)
    check_run_response = await mock_gh.post(
        "/repos/pangeo-forge/staged-recipes/check-runs",
        data=check_run_create_kwargs,
    )
    commit_sha = check_run_response["head_sha"]

    # now that the data is in the mock github backend, retrieve it
    response = await async_app_client.get(f"/feedstocks/1/commits/{commit_sha}/check-runs")
    json_ = response.json()
    assert json_["total_count"] == 1  # this value represents the number of check runs created
    for k in check_run_create_kwargs:
        assert json_["check_runs"][0][k] == check_run_create_kwargs[k]


@pytest.mark.parametrize(
    "hash_signature_problem,expected_response_detail",
    [
        ("missing", "Request does not include a GitHub hash signature header."),
        ("incorrect", "Request hash signature invalid."),
    ],
)
@pytest.mark.asyncio
async def test_receive_github_hook_unauthorized(
    async_app_client,
    hash_signature_problem,
    expected_response_detail,
):
    if hash_signature_problem == "missing":
        headers = {}
    elif hash_signature_problem == "incorrect":
        os.environ["GITHUB_WEBHOOK_SECRET"] = "foobar"
        headers = {"X-Hub-Signature-256": "abcdefg"}

    response = await async_app_client.post(
        "/github/hooks/",
        json={},
        headers=headers,
    )
    assert response.status_code == 401
    assert json.loads(response.text)["detail"] == expected_response_detail


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


def add_hash_signature(request: dict, webhook_secret: str):
    payload_bytes = bytes(json.dumps(request["payload"]), "utf-8")
    hash_signature = hmac.new(
        bytes(webhook_secret, encoding="utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    request["headers"].update({"X-Hub-Signature-256": f"sha256={hash_signature}"})
    return request


@pytest_asyncio.fixture
async def synchronize_request(
    webhook_secret,
    async_app_client,
    admin_key,
    request,
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

    yield add_hash_signature(request, webhook_secret)

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "synchronize_request",
    ["pangeo-forge/staged-recipes", "pangeo-forge/pangeo-forge.org"],
    indirect=True,
)
async def test_receive_synchronize_request(
    mocker,
    get_mock_github_session,
    webhook_secret,
    async_app_client,
    synchronize_request,
    private_key,
):
    os.environ["GITHUB_WEBHOOK_SECRET"] = webhook_secret
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app, "get_github_session", get_mock_github_session
    )

    mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)
    os.environ["PEM_FILE"] = private_key
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
        # TODO: fixturize expected_recipe_runs_response
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

        for k in expected_recipe_runs_response[0]:
            if k not in ["started_at", "completed_at"]:
                assert expected_recipe_runs_response[0][k] == recipe_runs_response.json()[0][k]

        # then assert that the check runs were created as expected
        commit_sha = recipe_runs_response.json()[0]["head_sha"]
        check_runs_response = await async_app_client.get(
            f"/feedstocks/1/commits/{commit_sha}/check-runs"
        )

        # TODO: fixturize expected_check_runs_response
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
                        "summary": "Recipe runs created at commit `abc`:\n- https://pangeo-forge.org/dashboard/recipe-run/1?feedstock_id=1",
                    },
                    "details_url": "https://pangeo-forge.org/",
                    "id": 0,
                    "conclusion": "success",
                    "completed_at": "2022-08-11T21:22:51Z",
                }
            ],
        }

        assert expected_check_runs_response["total_count"] == 1
        for k in expected_check_runs_response["check_runs"][0]:
            if k not in ["started_at", "completed_at"]:
                assert (
                    expected_check_runs_response["check_runs"][0][k]
                    == check_runs_response.json()["check_runs"][0][k]
                )


@pytest_asyncio.fixture
async def pr_merged_request(webhook_secret, request):

    headers = {"X-GitHub-Event": "pull_request"}
    payload = {
        "action": "closed",
        "pull_request": {
            "number": request.param["number"],
            "merged": True,
            "base": {
                "repo": {
                    "url": "https://api.github.com/repos/pangeo-forge/staged-recipes",
                    "full_name": "pangeo-forge/staged-recipes",
                    "owner": {
                        "login": "pangeo-forge",
                    },
                },
                "ref": "main",
            },
            "labels": [],
            "title": request.param["title"],
        },
    }
    request = {"headers": headers, "payload": payload}

    # setup database for this test - none required

    yield add_hash_signature(request, webhook_secret)

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pr_merged_request",
    [
        dict(number=1, title="Add XYZ awesome dataset"),
        dict(number=2, title="Cleanup: pangeo-forge/XYZ-feedstock"),
        dict(number=3, title="Update staged-recipes README"),
        dict(number=4, title="Update feedstock README"),
    ],
    indirect=True,
)
async def test_receive_pr_merged_request(
    mocker,
    get_mock_github_session,
    async_app_client,
    pr_merged_request,
):
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    # make sure that there are no feedstocks in the database to begin with
    existing_feedstocks = await async_app_client.get("/feedstocks/")
    assert existing_feedstocks.json() == []

    response = await async_app_client.post(
        "/github/hooks/",
        json=pr_merged_request["payload"],
        headers=pr_merged_request["headers"],
    )
    assert response.status_code == 202

    pr_title = pr_merged_request["payload"]["pull_request"]["title"]

    if pr_title == "Add XYZ awesome dataset":
        # if this pr added a feedstock, make sure it was added to the database
        feedstocks = await async_app_client.get("/feedstocks/")
        assert feedstocks.json()[0]["spec"] == "pangeo-forge/new-dataset-feedstock"

    if pr_title.startswith("Cleanup"):
        assert response.json()["message"] == "This is an automated cleanup PR. Skipping."

    if pr_title == "Update staged-recipes README" or pr_title == "Update feedstock README":
        assert response.json()["message"] == "Not a recipes PR. Skipping."
