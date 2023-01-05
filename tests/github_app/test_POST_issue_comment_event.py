import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session
from .mock_pangeo_forge_runner import get_mock_subprocess_executable


@pytest_asyncio.fixture
async def issue_comment_request_fixture(
    webhook_secret,
    async_app_client,
    api_key,
    request,
    staged_recipes_pulls_files,
):
    headers = {"X-GitHub-Event": "issue_comment"}
    payload = {
        "action": "created",
        "comment": {
            "body": request.param["body"],
            "reactions": {
                "url": (
                    "https://api.github.com/repos/"
                    f"{request.param['repo_full_name']}/issues/"
                    f"comments/{request.param['comment_id']}/reactions"
                ),
            },
        },
        "issue": {
            "pull_request": {
                "url": (
                    "https://api.github.com/repos/"
                    f"{request.param['repo_full_name']}/"
                    f"pulls/{request.param['pr_number']}"
                )
            },
        },
    }
    event_request = {"headers": headers, "payload": payload}

    # setup database
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
        json={"spec": "pangeo-forge/staged-recipes"},  # TODO: set dynamically
        headers=admin_headers,
    )
    assert feedstock_create_response.status_code == 200
    recipe_run_create_response = await async_app_client.post(
        "/recipe_runs/",
        json={
            "recipe_id": "liveocean",
            "bakery_id": 1,
            "feedstock_id": 1,
            "head_sha": "037542663cb7f7bc4a04777c90d85accbff01c8c",
            "version": "",
            "started_at": "2022-09-19T16:31:43",
            "completed_at": None,
            "conclusion": None,
            "status": "queued",
            "is_test": True,
            "dataset_type": "zarr",
            "dataset_public_url": None,
            "message": None,
        },
        headers=admin_headers,
    )
    assert recipe_run_create_response.status_code == 200

    # setup mock github
    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_pulls": {
            "pangeo-forge/staged-recipes": {
                1: {
                    "number": 1,
                    "head": {
                        "sha": "037542663cb7f7bc4a04777c90d85accbff01c8c",
                        "repo": {
                            "html_url": "https://github.com/contributor-username/staged-recipes",
                        },
                    },
                    "base": {
                        "repo": {
                            "url": "https://api.github.com/repos/pangeo-forge/staged-recipes",
                            "full_name": "pangeo-forge/staged-recipes",
                        }
                    },
                }
            }
        },
        "_pulls_files": {
            "pangeo-forge/staged-recipes": staged_recipes_pulls_files,
        },
    }

    yield add_hash_signature(event_request, webhook_secret), _MockGitHubBackend(**gh_backend_kws)

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "issue_comment_request_fixture",
    [
        dict(
            body="This is just a regular user comment.",
            repo_full_name="pangeo-forge/staged-recipes",
            comment_id=12345678,
            pr_number=1,
        ),
        dict(
            body="/run liveocean",
            repo_full_name="pangeo-forge/staged-recipes",
            comment_id=12345678,
            pr_number=1,
        ),
        dict(
            body="/run liveocean plus-some-unsupported-arg",
            repo_full_name="pangeo-forge/staged-recipes",
            comment_id=12345678,
            pr_number=1,
        ),
        dict(
            body="/run-recipe-test liveocean",
            repo_full_name="pangeo-forge/staged-recipes",
            comment_id=12345678,
            pr_number=1,
        ),
    ],
    indirect=True,
)
async def test_receive_issue_comment_request(
    mocker,
    async_app_client,
    issue_comment_request_fixture,
):
    issue_comment_request, gh_backend = issue_comment_request_fixture
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    mocker.patch.object(
        pangeo_forge_orchestrator.configurables.spawner,
        "get_subprocess_executable",
        get_mock_subprocess_executable,
    )

    recipe_run = await async_app_client.get("/recipe_runs/1")
    assert recipe_run.json()["status"] == "queued"

    response = await async_app_client.post(
        "/github/hooks/",
        json=issue_comment_request["payload"],
        headers=issue_comment_request["headers"],
    )

    comment_body = issue_comment_request["payload"]["comment"]["body"]
    if not comment_body.startswith("/"):
        assert response.json()["message"] == "Comment is not a slash command."
    else:
        if len(comment_body.split()) > 2:
            # this slash command has too many args,
            # so it's an HTTP 400 Bad Request
            assert response.status_code == 400
        elif comment_body.split()[0] != "/run":
            # this is not a supported slash command
            assert response.status_code == 400
        else:
            recipe_run = await async_app_client.get("/recipe_runs/1")
            assert recipe_run.json()["status"] == "in_progress"
