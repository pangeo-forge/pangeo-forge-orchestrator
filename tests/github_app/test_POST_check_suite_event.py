import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from .fixtures import _MockGitHubBackend, add_hash_signature, get_mock_github_session


@pytest_asyncio.fixture
async def check_suite_request_fixture(webhook_secret):
    headers = {"X-GitHub-Event": "check_suite"}
    payload = {}
    event_request = {"headers": headers, "payload": payload}

    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
    }
    yield add_hash_signature(event_request, webhook_secret), _MockGitHubBackend(**gh_backend_kws)


@pytest.mark.asyncio
async def test_receive_check_suite_request(
    mocker,
    async_app_client,
    check_suite_request_fixture,
):
    check_suite_request, gh_backend = check_suite_request_fixture
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    response = await async_app_client.post(
        "/github/hooks/",
        json=check_suite_request["payload"],
        headers=check_suite_request["headers"],
    )
    assert response.json() == {"status": "ok"}
