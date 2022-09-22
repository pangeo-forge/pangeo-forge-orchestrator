import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session


@pytest_asyncio.fixture
async def unimplemented_request_fixture(webhook_secret, request):
    headers = {"X-GitHub-Event": request.param["event"]}
    payload = {}
    event_request = {"headers": headers, "payload": payload}

    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
    }
    yield add_hash_signature(event_request, webhook_secret), _MockGitHubBackend(**gh_backend_kws)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unimplemented_request_fixture",
    [dict(event="some_unimplemented_event")],
    indirect=True,
)
async def test_receive_check_suite_request(
    mocker,
    async_app_client,
    unimplemented_request_fixture,
):
    unimplemented_request, gh_backend = unimplemented_request_fixture
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    response = await async_app_client.post(
        "/github/hooks/",
        json=unimplemented_request["payload"],
        headers=unimplemented_request["headers"],
    )
    assert response.status_code == 501
    assert response.json()["detail"] == "No handling implemented for this event type."
