import json
import random
from urllib.parse import parse_qs, urlencode

import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session


@pytest_asyncio.fixture
async def dataflow_request_fixture(
    webhook_secret,
    api_key,
    async_app_client,
    request,
):
    headers = {"X-GitHub-Event": "dataflow"}
    payload = {
        "action": "completed",
        "recipe_run_id": request.param["recipe_run_id"],
        "conclusion": request.param["conclusion"],
    }
    event_request = {
        "headers": headers,
        # special case for dataflow payload, to replicate how it is actually sent.
        # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
        # for further detail. ideally, this special casing wll be removed eventually.
        "payload": urlencode(payload, doseq=True),
    }

    # setup database for this test
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
        json={"spec": request.param["feedstock_spec"]},
        headers=admin_headers,
    )
    assert feedstock_create_response.status_code == 200
    recipe_run_create_response = await async_app_client.post(
        "/recipe_runs/",
        json={
            "recipe_id": "eooffshore_ics_cmems_WIND_GLO_WIND_L3_NRT_OBSERVATIONS_012_002_MetOp_ASCAT",
            "bakery_id": 1,
            "feedstock_id": 1,
            "head_sha": "037542663cb7f7bc4a04777c90d85accbff01c8c",
            "version": "",
            "started_at": "2022-09-19T16:31:43",
            "completed_at": None,
            "conclusion": None,
            "status": "in_progress",
            "is_test": request.param["is_test"],
            "dataset_type": "zarr",
            "dataset_public_url": None,
            "message": request.param["recipe_run_message"],
        },
        headers=admin_headers,
    )
    assert recipe_run_create_response.status_code == 200

    # create gh backend
    backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_pulls": [
            {
                "comments_url": (
                    "https://api.github.com/repos/"
                    f"{request.param['feedstock_spec']}/issues/1347/comments"
                ),
                "head": {
                    "sha": "037542663cb7f7bc4a04777c90d85accbff01c8c",
                },
            },
        ],
    }

    yield add_hash_signature(event_request, webhook_secret), _MockGitHubBackend(**backend_kws)

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dataflow_request_fixture",
    [
        dict(
            feedstock_spec="pangeo-forge/staged-recipes",
            recipe_run_id=1,
            is_test=True,
            recipe_run_message=None,
            conclusion="unsupported-conclusion",
        ),
        dict(
            feedstock_spec="pangeo-forge/staged-recipes",
            recipe_run_id=1,
            is_test=True,
            recipe_run_message=None,
            conclusion="failure",
        ),
        dict(
            feedstock_spec="pangeo-forge/staged-recipes",
            recipe_run_id=1,
            is_test=True,
            recipe_run_message=None,
            conclusion="success",
        ),
        dict(
            feedstock_spec="pangeo-forge/gpcp-feedstock",
            recipe_run_id=1,
            is_test=False,
            recipe_run_message=json.dumps(
                {
                    "deployment_id": random.randint(10_000, 11_000),
                    "environment_url": (
                        "https://pangeo-forge.org/dashboard/recipe-run/1?feedstock_id=1"
                    ),
                }
            ),
            conclusion="failure",
        ),
        dict(
            feedstock_spec="pangeo-forge/gpcp-feedstock",
            recipe_run_id=1,
            is_test=False,
            recipe_run_message=json.dumps(
                {
                    "deployment_id": random.randint(10_000, 11_000),
                    "environment_url": (
                        "https://pangeo-forge.org/dashboard/recipe-run/1?feedstock_id=1"
                    ),
                }
            ),
            conclusion="success",
        ),
    ],
    indirect=True,
)
async def test_receive_dataflow_request(
    mocker,
    async_app_client,
    dataflow_request_fixture,
):
    dataflow_request, gh_backend = dataflow_request_fixture
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    # special case for dataflow payload, to replicate how it is actually sent.
    # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
    # for further detail. ideally, this special casing wll be removed eventually.
    qs = parse_qs(dataflow_request["payload"])
    decoded_payload = {k: v.pop(0) for k, v in qs.items()}

    # first, assert initial state is correct
    recipe_run_response = await async_app_client.get(
        f"/recipe_runs/{decoded_payload['recipe_run_id']}",
    )
    assert recipe_run_response.status_code == 200
    assert recipe_run_response.json()["status"] == "in_progress"
    assert recipe_run_response.json()["conclusion"] is None

    # okay, now actually simulate the event
    response = await async_app_client.post(
        "/github/hooks/",
        # note, for all other tests we pass a `json` dict, but here we use `data`, to reflect the
        # special casing for dataflow referenced in comments above in this module. it would be
        # great to unify this with the other endpoints, which would require a change to the
        # `dataflow-status-monitoring` submodule's `src/main.py`
        data=dataflow_request["payload"],
        headers=dataflow_request["headers"],
    )

    if decoded_payload["conclusion"] == "unsupported-conclusion":
        assert response.status_code == 400
        assert json.loads(response.text)["detail"] == (
            "No handling implemented for payload['conclusion'] = 'unsupported-conclusion'."
        )

    else:
        recipe_run_response = await async_app_client.get(
            f"/recipe_runs/{decoded_payload['recipe_run_id']}",
        )
        assert recipe_run_response.status_code == 200
        assert recipe_run_response.json()["status"] == "completed"
        assert recipe_run_response.json()["conclusion"] == decoded_payload["conclusion"]
