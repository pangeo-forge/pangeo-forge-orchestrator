import hashlib
import hmac
import json
from typing import TypedDict, Union

import httpx
import pytest
import pytest_asyncio

import pangeo_forge_orchestrator


class EventRequest(TypedDict):
    headers: dict
    payload: Union[str, dict]  # union because of dataflow payload edge case


def add_hash_signature(request: EventRequest, webhook_secret: str):
    if request["headers"]["X-GitHub-Event"] != "dataflow":
        payload_bytes = bytes(json.dumps(request["payload"]), "utf-8")
    else:
        # special case for dataflow payload, to replicate how it is actually sent.
        # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
        # for further detail. ideally, this special casing wll be removed eventually.
        payload_bytes = request["payload"].encode("utf-8")  # type: ignore

    hash_signature = hmac.new(
        bytes(webhook_secret, encoding="utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    request["headers"].update({"X-Hub-Signature-256": f"sha256={hash_signature}"})
    return request


@pytest_asyncio.fixture
async def synchronize_request_fixture(
    webhook_secret,
    request,
    staged_recipes_pulls_files,
    app_hook_config_url,
):
    headers = {"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "123-456-789"}
    payload = {
        "action": "synchronize",
        "pull_request": {
            "number": request.param["number"],
            "base": {
                "repo": {
                    "html_url": f"https://github.com/{request.param['base_repo_full_name']}",
                    "url": f"https://api.github.com/repos/{request.param['base_repo_full_name']}",
                    "full_name": request.param["base_repo_full_name"],
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
            "title": request.param["title"],
        },
    }
    request = {"headers": headers, "payload": payload}

    # setup mock github backend for this test

    mock_responses = {
        "/app/installations": httpx.Response(200, json=[{"id": 1234567}]),
        f"/app/installations/{1234567}/access_tokens": (
            httpx.Response(200, json={"token": "abcdefghijklmnop"})
        ),
        "/repos/pangeo-forge/staged-recipes/check-runs": (
            httpx.Response(200, json={"id": 1234567890})
        ),
    }

    async def handler(request: httpx.Request):
        return mock_responses[request.url.path]

    mounts = {"https://api.github.com": httpx.MockTransport(handler)}

    # gh_backend_kws = {
    #     "_app_installations": [{"id": 1234567}],
    #     "_accessible_repos": [
    #         {"full_name": "pangeo-forge/staged-recipes"},
    #         {"full_name": "pangeo-forge/pangeo-forge.org"},
    #     ],
    #     "_repositories": {
    #         "pangeo-forge/staged-recipes": {"id": 987654321},
    #     },
    #     "_app_hook_config_url": app_hook_config_url,
    #     "_check_runs": list(),
    #     "_pulls_files": {
    #         "pangeo-forge/staged-recipes": staged_recipes_pulls_files,
    #     },
    # }
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
                    "summary": "",
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
        expected_check_runs_response,
        mounts,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "synchronize_request_fixture",
    [
        dict(
            number=1,
            base_repo_full_name="pangeo-forge/staged-recipes",
            title="Add XYZ awesome dataset",
        ),
    ],
    indirect=True,
)
async def test_receive_synchronize_request(
    mocker,
    async_app_client,
    synchronize_request_fixture,
):
    (
        synchronize_request,
        expected_check_runs_response,
        mounts,
    ) = synchronize_request_fixture

    def get_mock_http_session():
        mock_session = httpx.AsyncClient(mounts=mounts)
        return mock_session

    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_http_session",
        get_mock_http_session,
    )

    # mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)
    response = await async_app_client.post(
        "/github/hooks/",
        json=synchronize_request["payload"],
        headers=synchronize_request["headers"],
    )
    assert response.status_code == 202

    # then assert that the check runs were created as expected
    # commit_sha = recipe_runs_response.json()[0]["head_sha"]
    # check_runs_response = await async_app_client.get(
    #     f"/feedstocks/1/commits/{commit_sha}/check-runs"
    # )

    # assert expected_check_runs_response["total_count"] == 1
    # for k in expected_check_runs_response["check_runs"][0]:
    #     if k not in ["started_at", "completed_at"]:
    #         assert (
    #             expected_check_runs_response["check_runs"][0][k]
    #             == check_runs_response.json()["check_runs"][0][k]
    #         )
