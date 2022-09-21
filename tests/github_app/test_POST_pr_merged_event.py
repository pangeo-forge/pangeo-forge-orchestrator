import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session


@pytest_asyncio.fixture
async def pr_merged_request_fixture(
    webhook_secret,
    request,
    staged_recipes_pulls_files,
):

    headers = {"X-GitHub-Event": "pull_request"}
    payload = {
        "action": "closed",
        "pull_request": {
            "number": request.param["number"],
            "merged": True,
            "base": {
                "repo": {
                    "url": f"https://api.github.com/repos/{request.param['base_repo_full_name']}",
                    "full_name": request.param["base_repo_full_name"],
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
    event_request = {"headers": headers, "payload": payload}

    # create gh backend
    if request.param["base_repo_full_name"] == "pangeo-forge/staged-recipes":
        _pulls_files = {"pangeo-forge/staged-recipes": staged_recipes_pulls_files}

    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_pulls_files": _pulls_files,
    }

    yield add_hash_signature(event_request, webhook_secret), _MockGitHubBackend(**gh_backend_kws)

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pr_merged_request_fixture",
    [
        dict(
            number=1,
            base_repo_full_name="pangeo-forge/staged-recipes",
            title="Add XYZ awesome dataset",
        ),
        dict(
            number=2,
            base_repo_full_name="pangeo-forge/staged-recipes",
            title="Cleanup: pangeo-forge/XYZ-feedstock",
        ),
        dict(
            number=3,
            base_repo_full_name="pangeo-forge/staged-recipes",
            title="Update staged-recipes README",
        ),
        dict(
            number=4,
            base_repo_full_name="pangeo-forge/staged-recipes",
            title="Update feedstock README",
        ),
        # dict(
        #    number=1,
        #    title=""
        # ),
    ],
    indirect=True,
)
async def test_receive_pr_merged_request(
    mocker,
    async_app_client,
    pr_merged_request_fixture,
):
    pr_merged_request, gh_backend = pr_merged_request_fixture
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
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
