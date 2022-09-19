import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import add_hash_signature


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
