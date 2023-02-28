from datetime import datetime

import pytest
import pytest_asyncio

import pangeo_forge_orchestrator

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
async def test_get_all_deliveries(
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


@pytest_asyncio.fixture
async def feedstock_deliveries_fixture(api_key, async_app_client, app_hook_deliveries):
    admin_headers = {"X-API-Key": api_key}
    feedstock_create_response = await async_app_client.post(
        "/feedstocks/",
        json={"spec": "pangeo-forge/staged-recipes"},
        headers=admin_headers,
    )
    assert feedstock_create_response.status_code == 200

    gh_backend_kws = {
        "_app_installations": [{"id": 1234567}],
        "_accessible_repos": [
            {"full_name": "pangeo-forge/staged-recipes"},
        ],
        "_app_hook_deliveries": app_hook_deliveries,
        "_repositories": {
            "pangeo-forge/staged-recipes": {"id": app_hook_deliveries[0]["repository_id"]},
        },
    }
    yield app_hook_deliveries, _MockGitHubBackend(**gh_backend_kws)


@pytest.mark.asyncio
async def test_get_feedstock_deliveries(
    mocker,
    feedstock_deliveries_fixture,
    async_app_client,
):
    app_hook_deliveries, gh_backend = feedstock_deliveries_fixture
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session(gh_backend),
    )
    response = await async_app_client.get("/feedstocks/1/deliveries")
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
async def check_run_create_kwargs(api_key, async_app_client):
    # setup database
    admin_headers = {"X-API-Key": api_key}
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


@pytest.mark.asyncio
async def test_get_feedstock_check_runs(
    mocker,
    check_run_create_kwargs,
    async_app_client,
):
    gh_backend = _MockGitHubBackend(
        _app_installations=[{"id": 1234567}],
        _repositories={"pangeo-forge/staged-recipes": {"id": 987654321}},
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
