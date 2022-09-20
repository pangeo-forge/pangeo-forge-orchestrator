import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session


@pytest.fixture
def staged_recipes_pr_1_files():
    return [
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
    ]


@pytest.fixture
def staged_recipes_pr_2_files(staged_recipes_pr_1_files):
    # This PR is the automated cleanup PR following merge of PR 1. I think that means the
    # `files` JSON is more-or-less the same? Except that the contents would be different,
    # of course, but our fixtures don't capture that level of detail yet.
    return staged_recipes_pr_1_files


@pytest.fixture
def staged_recipes_pr_3_files():
    return [
        {
            "filename": "README.md",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/staged-recipes/"
                "contents/README.md"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def staged_recipes_pr_4_files():
    return [
        {
            "filename": "README.md",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/dataset-feedstock/"
                "contents/README.md"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def staged_recipes_pulls_files(
    staged_recipes_pr_1_files,
    staged_recipes_pr_2_files,
    staged_recipes_pr_3_files,
    staged_recipes_pr_4_files,
):
    return {
        1: staged_recipes_pr_1_files,
        2: staged_recipes_pr_2_files,
        3: staged_recipes_pr_3_files,
        4: staged_recipes_pr_4_files,
    }


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

    # create gh backend
    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_pulls_files": {
            "pangeo-forge/staged-recipes": staged_recipes_pulls_files,
        },
    }

    yield add_hash_signature(request, webhook_secret), _MockGitHubBackend(**gh_backend_kws)

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pr_merged_request_fixture",
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
