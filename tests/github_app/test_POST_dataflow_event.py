import json
from urllib.parse import parse_qs, urlencode

import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import add_hash_signature


def test_webhook_url_to_job_name_encode_decode():
    pass


@pytest_asyncio.fixture
async def dataflow_request(webhook_secret, request):

    headers = {"X-GitHub-Event": "dataflow"}
    payload = {
        "action": "completed",
        "recipe_run_id": request.param["recipe_run_id"],
        "conclusion": request.param["conclusion"],
    }
    request = {
        "headers": headers,
        # special case for dataflow payload, to replicate how it is actually sent.
        # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
        # for further detail. ideally, this special casing wll be removed eventually.
        "payload": urlencode(payload, doseq=True),
    }

    # setup database for this test - none required

    yield add_hash_signature(request, webhook_secret)

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dataflow_request",
    [
        dict(recipe_run_id=1, conclusion="unsupported-conclusion"),
        dict(recipe_run_id=1, conclusion="failure"),
        dict(recipe_run_id=1, conclusion="success"),
    ],
    indirect=True,
)
async def test_receive_dataflow_request(
    mocker,
    get_mock_github_session,
    async_app_client,
    dataflow_request,
):
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    # special case for dataflow payload, to replicate how it is actually sent.
    # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
    # for further detail. ideally, this special casing wll be removed eventually.
    qs = parse_qs(dataflow_request["payload"])
    decoded_payload = {k: v.pop(0) for k, v in qs.items()}

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
        pass
