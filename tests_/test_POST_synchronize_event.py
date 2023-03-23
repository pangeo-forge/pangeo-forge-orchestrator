import hashlib
import hmac
import json
import subprocess
from typing import TypedDict, Union

import httpx
import pytest
import pytest_asyncio

from pangeo_forge_orchestrator.api import app
from pangeo_forge_orchestrator.routers.github_app import get_http_session


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


def mock_subprocess_check_output(cmd: list[str]):
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
        elif cmd[1] == "bake":
            return b'{"message": "Submitted job 2022-11-02_09_47_12-7631717319482580875 for recipe NASA-SMAP-SSS/RSS/monthly","recipe": "NASA-SMAP-SSS/RSS/monthly","job_name": "a6170692e70616e67656f2d666f7267652e6f7267251366","job_id": "2022-11-02_09_47_12-7631717319482580875","status": "submitted"}'
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
        "/app/installations": {
            "GET": httpx.Response(200, json=[{"id": 1234567}]),
        },
        f"/app/installations/{1234567}/access_tokens": {
            "POST": httpx.Response(200, json={"token": "abcdefghijklmnop"}),
        },
        "/repos/pangeo-forge/staged-recipes/check-runs": {
            "POST": httpx.Response(200, json={"id": 1234567890})
        },
        "/repos/pangeo-forge/staged-recipes/pulls/1/files": {
            "GET": httpx.Response(
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
        },
        "/repos/pangeo-forge/staged-recipes/check-runs/1234567890": {
            "PATCH": httpx.Response(200),
        },
    }

    async def handler(request: httpx.Request):
        return mock_responses[request.url.path][request.method]

    mounts = {"https://api.github.com": httpx.MockTransport(handler)}

    def get_mock_http_session():
        mock_session = httpx.AsyncClient(mounts=mounts)
        return mock_session

    # https://fastapi.tiangolo.com/advanced/testing-dependencies/#testing-dependencies-with-overrides
    app.dependency_overrides[get_http_session] = get_mock_http_session

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
    )

    # cleanup overrides set above
    app.dependency_overrides = {}
    assert not app.dependency_overrides


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
    ) = synchronize_request_fixture

    mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)
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
