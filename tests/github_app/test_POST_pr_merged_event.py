import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session
from .mock_pangeo_forge_runner import get_mock_subprocess_executable


@pytest.fixture
def gpcp_feedstock_pr_1_files():
    return [
        {
            "filename": "feedstock/recipe.py",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/gpcp-feedstock/"
                "contents/feedstock/recipe.py"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def gpcp_feedstock_pr_2_files():
    return [
        {
            "filename": "README.md",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/gpcp-feedstock/"
                "contents/README.md"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def gpcp_feedstock_pulls_files(gpcp_feedstock_pr_1_files, gpcp_feedstock_pr_2_files):
    return {1: gpcp_feedstock_pr_1_files, 2: gpcp_feedstock_pr_2_files}


@pytest.fixture
def frontend_pr_1_files():
    return [
        {
            "filename": "src/theme/index.js",
            "contents_url": (
                "https://api.github.com/repos/pangeo-forge/pangeo-forge.org/"
                "contents/src/theme/index.js"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def frontend_pulls_files(frontend_pr_1_files):
    return {1: frontend_pr_1_files}


@pytest_asyncio.fixture
async def pr_merged_request_fixture(
    webhook_secret,
    request,
    staged_recipes_pulls_files,
    gpcp_feedstock_pulls_files,
    frontend_pulls_files,
    api_key,
    async_app_client,
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
    if request.param["base_repo_full_name"].endswith("-feedstock"):
        # these payload fields are not used for staged-recipes merges
        payload["pull_request"]["base"]["repo"].update(
            {"html_url": f"https://github.com/{request.param['base_repo_full_name']}"}
        )
        payload["pull_request"].update({"merge_commit_sha": "654321qwerty0987"})

        # staged-recipes merges don't need this database state
        admin_headers = {"X-API-Key": api_key}
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
            json={"spec": request.param["base_repo_full_name"]},
            headers=admin_headers,
        )
        assert feedstock_create_response.status_code == 200

    event_request = {"headers": headers, "payload": payload}

    # create gh backend
    if request.param["base_repo_full_name"] == "pangeo-forge/staged-recipes":
        _pulls_files = {"pangeo-forge/staged-recipes": staged_recipes_pulls_files}

    elif request.param["base_repo_full_name"].endswith("-feedstock"):
        _pulls_files = {"pangeo-forge/gpcp-feedstock": gpcp_feedstock_pulls_files}

    elif request.param["base_repo_full_name"] == "pangeo-forge/pangeo-forge.org":
        _pulls_files = {"pangeo-forge/pangeo-forge.org": frontend_pulls_files}

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
        dict(
            number=1,
            base_repo_full_name="pangeo-forge/gpcp-feedstock",
            title="Fix date range in feedstock/recipe.py",
        ),
        dict(
            number=2,
            base_repo_full_name="pangeo-forge/gpcp-feedstock",
            title="Update gpcp-feedstock README",
        ),
        dict(
            number=1,
            base_repo_full_name="pangeo-forge/pangeo-forge.org",
            title="Update styles on frontend website",
        ),
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
    base_repo_full_name = pr_merged_request["payload"]["pull_request"]["base"]["repo"]["full_name"]

    if base_repo_full_name == "pangeo-forge/staged-recipes":
        # make sure that there are no feedstocks in the database to begin with
        existing_feedstocks = await async_app_client.get("/feedstocks/")
        assert existing_feedstocks.json() == []
    elif base_repo_full_name.endswith("-feedstock"):
        mocker.patch.object(
            pangeo_forge_orchestrator.configurables.spawner,
            "get_subprocess_executable",
            get_mock_subprocess_executable,
        )

    response = await async_app_client.post(
        "/github/hooks/",
        json=pr_merged_request["payload"],
        headers=pr_merged_request["headers"],
    )
    assert response.status_code == 202

    if not base_repo_full_name.endswith("staged-recipes") and not base_repo_full_name.endswith(
        "-feedstock"
    ):
        assert response.json() == {
            "status": "skip",
            "message": "This not a -feedstock repo. Skipping.",
        }

    pr_title = pr_merged_request["payload"]["pull_request"]["title"]
    if pr_title == "Add XYZ awesome dataset":
        # if this pr added a feedstock, make sure it was added to the database
        feedstocks = await async_app_client.get("/feedstocks/")
        assert feedstocks.json()[0]["spec"] == "pangeo-forge/new-dataset-feedstock"

    if pr_title.startswith("Cleanup"):
        assert response.json()["message"] == "This is an automated cleanup PR. Skipping."

    if pr_title == "Update staged-recipes README" or pr_title == "Update gpcp-feedstock README":
        assert response.json()["message"] == "Not a recipes PR. Skipping."
