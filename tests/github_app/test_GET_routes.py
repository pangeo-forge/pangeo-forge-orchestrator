import os
from datetime import datetime

import pytest
import pytest_asyncio

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.http import http_session

from ..conftest import clear_database


@pytest.mark.asyncio
async def test_get_deliveries(
    mocker,
    private_key,
    get_mock_github_session,
    app_hook_deliveries,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    response = await async_app_client.get("/github/hooks/deliveries")
    assert response.status_code == 200
    assert response.json() == app_hook_deliveries


@pytest.mark.asyncio
async def test_get_delivery(
    mocker,
    private_key,
    get_mock_github_session,
    app_hook_deliveries,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
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
    private_key,
    get_mock_github_session,
    check_run_create_kwargs,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )

    # populate mock github backend with check runs for the feedstock (only 1 for now)
    mock_gh = get_mock_github_session(http_session)
    check_run_response = await mock_gh.post(
        "/repos/pangeo-forge/staged-recipes/check-runs",
        data=check_run_create_kwargs,
    )
    commit_sha = check_run_response["head_sha"]

    # now that the data is in the mock github backend, retrieve it
    response = await async_app_client.get(f"/feedstocks/1/commits/{commit_sha}/check-runs")
    json_ = response.json()
    assert json_["total_count"] == 1  # this value represents the number of check runs created
    for k in check_run_create_kwargs:
        assert json_["check_runs"][0][k] == check_run_create_kwargs[k]
