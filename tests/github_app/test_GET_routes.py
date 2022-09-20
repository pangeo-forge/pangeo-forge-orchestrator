from datetime import datetime

import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, get_mock_github_session


@pytest.fixture
def app_hook_deliveries():
    """Webhook deliveries to the GitHub App. Examples copied from real delivieres to the app."""

    return [
        {
            "id": 24081517883,
            "guid": "04d4b7f0-0f85-11ed-8539-b846a7d005af",
            "delivered_at": "2022-07-29T21:25:50Z",
            "redelivery": "false",
            "duration": 0.03,
            "status": "Invalid HTTP Response: 501",
            "status_code": 501,
            "event": "check_suite",
            "action": "requested",
            "installation_id": 27724604,
            "repository_id": 518221894,
            "url": "",
        },
        {
            "id": 24081517383,
            "guid": "04460c80-0f85-11ed-8fc2-f8b6d8b7d25d",
            "delivered_at": "2022-07-29T21:25:50Z",
            "redelivery": "false",
            "duration": 0.04,
            "status": "OK",
            "status_code": 202,
            "event": "pull_request",
            "action": "synchronize",
            "installation_id": 27724604,
            "repository_id": 518221894,
            "url": "",
        },
    ]


@pytest.mark.asyncio
async def test_get_deliveries(
    mocker,
    app_hook_deliveries,
    async_app_client,
):
    gh_backend = _MockGitHubBackend(_app_hook_deliveries=app_hook_deliveries)
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    response = await async_app_client.get("/github/hooks/deliveries")
    assert response.status_code == 200
    assert response.json() == app_hook_deliveries


@pytest.mark.asyncio
async def test_get_delivery(
    mocker,
    app_hook_deliveries,
    async_app_client,
):
    gh_backend = _MockGitHubBackend(_app_hook_deliveries=app_hook_deliveries)
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    for delivery in app_hook_deliveries:
        id_ = delivery["id"]
        response = await async_app_client.get(f"/github/hooks/deliveries/{id_}")
        assert response.status_code == 200
        assert response.json() == delivery


@pytest_asyncio.fixture
async def check_run_create_kwargs(admin_key, async_app_client):
    # setup database
    admin_headers = {"X-API-Key": admin_key}
    fstock_response = await async_app_client.post(
        "/feedstocks/",
        json={"spec": "pangeo-forge/staged-recipes"},  # TODO: set dynamically
        headers=admin_headers,
    )
    assert fstock_response.status_code == 200

    yield dict(
        name="synchronize",
        head_sha="abcdefg",  # TODO: fixturize
        status="in_progress",
        started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        output=dict(
            title="Syncing latest commit to Pangeo Forge Cloud",
            summary="",  # required
        ),
        details_url="https://pangeo-forge.org/",  # TODO: make this more specific.
    )

    # database teardown
    clear_database()


@pytest.mark.asyncio
async def test_get_feedstock_check_runs(
    mocker,
    check_run_create_kwargs,
    async_app_client,
):
    gh_backend = _MockGitHubBackend(
        _app_installations=[{"id": 1234567}],
        _accessible_repos=[{"full_name": "pangeo-forge/staged-recipes"}],
        _check_runs=[check_run_create_kwargs],
    )
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    response = await async_app_client.get(
        f"/feedstocks/1/commits/{check_run_create_kwargs['head_sha']}/check-runs"
    )
    json_ = response.json()
    assert json_["total_count"] == 1  # this value represents the number of check runs created
    for k in check_run_create_kwargs:
        assert json_["check_runs"][0][k] == check_run_create_kwargs[k]
