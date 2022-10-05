import json
import subprocess
import uuid
from typing import List

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlmodel import Session

from pangeo_forge_orchestrator.config import get_config
from pangeo_forge_orchestrator.database import engine
from pangeo_forge_orchestrator.models import MODELS
from pangeo_forge_orchestrator.routers.logs import (
    get_logs,
    job_name_from_recipe_run,
    secret_str_vals_from_basemodel,
)

from ..conftest import clear_database


@pytest.mark.parametrize("bakery_name", ["pangeo-ldeo-nsf-earthcube"])
def test_secret_str_vals_from_basemodel(bakery_name):
    bakery_config = get_config().bakeries[bakery_name]
    bakery_secrets = secret_str_vals_from_basemodel(bakery_config)
    assert bakery_secrets == [
        json.loads(bakery_config.TargetStorage.fsspec_args.json())["key"],
        json.loads(bakery_config.TargetStorage.fsspec_args.json())["secret"],
    ]


@pytest.mark.parametrize(
    "message, expected_error",
    [
        ('{"job_name": "123"}', None),
        ('{"job_id": "123"}', KeyError),
        ('"job_name": "123"', json.JSONDecodeError),
    ],
)
def test_job_name_from_recipe_run(message, expected_error):
    recipe_run_kws = {
        "recipe_id": "liveocean",
        "bakery_id": 1,
        "feedstock_id": 1,
        "head_sha": "35d889f7c89e9f0d72353a0649ed1cd8da04826b",
        "version": "",
        "started_at": "2022-09-19T16:31:43",
        "completed_at": None,
        "conclusion": None,
        "status": "in_progress",
        "is_test": True,
        "dataset_type": "zarr",
        "dataset_public_url": None,
        "message": message,
        "id": 1,
    }
    recipe_run = MODELS["recipe_run"].table(**recipe_run_kws)
    if not expected_error:
        job_name = job_name_from_recipe_run(recipe_run)
        assert job_name == json.loads(message)["job_name"]
    else:
        with pytest.raises(HTTPException):
            job_name_from_recipe_run(recipe_run)


@pytest_asyncio.fixture
async def get_logs_fixture(
    api_key,
    async_app_client,
    request,
):
    admin_headers = {"X-API-Key": api_key}
    bakery_create_response = await async_app_client.post(
        "/bakeries/",
        json={
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
    recipe_run_kws = {
        "recipe_id": request.param["recipe_id"],
        "bakery_id": 1,
        "feedstock_id": 1,
        "head_sha": request.param["commit"],
        "version": "",
        "started_at": "2022-09-19T16:31:43",
        "completed_at": None,
        "conclusion": request.param["conclusion"],
        "status": request.param["status"],
        "is_test": True,
        "dataset_type": "zarr",
        "dataset_public_url": None,
        "message": request.param["message"],
        "id": 1,
    }
    recipe_run_response = await async_app_client.post(
        "/recipe_runs/",
        json=recipe_run_kws,
        headers=admin_headers,
    )
    assert recipe_run_response.status_code == 200
    yield (
        admin_headers,
        request.param["gcloud_logging_response"],
        request.param["feedstock_spec"],
        request.param["commit"],
        request.param["recipe_id"],
    )
    # database teardown
    clear_database()


gcloud_logging_responses = [
    json.dumps(dict(message="[worker] here's some normal logging with no secrets")),
    json.dumps(dict(message=f"[worker] a secret token={uuid.uuid4().hex}")),
]
logs_fixture_indirect_params = [
    dict(
        message='{"job_name": "abc"}',
        feedstock_spec="pangeo-forge/staged-recipes",
        commit="35d889f7c89e9f0d72353a0649ed1cd8da04826b",
        recipe_id="liveocean",
        gcloud_logging_response=response,
        status="completed",
        conclusion="failure",
    )
    for response in gcloud_logging_responses
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "get_logs_fixture",
    logs_fixture_indirect_params,
    indirect=True,
)
async def test_get_logs(mocker, get_logs_fixture, async_app_client):

    (
        _,
        gcloud_logging_response,
        _,
        _,
        _,
    ) = get_logs_fixture

    def mock_fetch_logs_call(cmd: List[str]):
        return bytes(gcloud_logging_response, encoding="utf-8")

    mocker.patch.object(subprocess, "check_output", mock_fetch_logs_call)

    recipe_run_response = await async_app_client.get("/recipe_runs/1")
    recipe_run_kws = {
        # drop extended response fields
        k: v
        for k, v in recipe_run_response.json().items()
        if k not in ["bakery", "feedstock"]
    }
    recipe_run = MODELS["recipe_run"].table(**recipe_run_kws)
    with Session(engine) as db_session:
        logs = get_logs(
            job_name=json.loads(recipe_run.message)["job_name"],
            source="worker",
            recipe_run=recipe_run,
            db_session=db_session,
            # severity="ERROR",
            # limit=1,
        )
    assert logs == gcloud_logging_response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "get_logs_fixture",
    logs_fixture_indirect_params,
    indirect=True,
)
async def test_get_logs_via_recipe_run_id(
    mocker,
    get_logs_fixture,
    async_app_client,
):
    admin_headers, gcloud_logging_response, *_ = get_logs_fixture

    def mock_gcloud_logging_call(cmd: List[str]):
        return bytes(gcloud_logging_response, encoding="utf-8")

    mocker.patch.object(subprocess, "check_output", mock_gcloud_logging_call)

    response = await async_app_client.get(
        "/recipe_runs/1/logs",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.text == gcloud_logging_response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "get_logs_fixture",
    logs_fixture_indirect_params,
    indirect=True,
)
async def test_get_logs_human_readable_method(
    mocker,
    get_logs_fixture,
    async_app_client,
):
    (
        admin_headers,
        gcloud_logging_response,
        feedstock_spec,
        commit,
        recipe_id,
    ) = get_logs_fixture

    def mock_gcloud_logging_call(cmd: List[str]):
        return bytes(gcloud_logging_response, encoding="utf-8")

    mocker.patch.object(subprocess, "check_output", mock_gcloud_logging_call)

    response = await async_app_client.get(
        f"/feedstocks/{feedstock_spec}/{commit}/{recipe_id}/logs",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.text == gcloud_logging_response
