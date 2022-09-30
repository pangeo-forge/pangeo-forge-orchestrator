import json
import subprocess
from textwrap import dedent
from typing import List

import pytest
import pytest_asyncio
from fastapi import HTTPException

from pangeo_forge_orchestrator.models import MODELS
from pangeo_forge_orchestrator.routers.logs import get_logs, job_id_from_recipe_run

from ..conftest import clear_database


@pytest.mark.parametrize(
    "message, expected_error",
    [
        ('{"job_id": "123"}', None),
        ('{"job_name": "123"}', KeyError),
        ('"job_id": "123"', json.JSONDecodeError),
    ],
)
def test_job_id_from_recipe_run(message, expected_error):
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
        job_id = job_id_from_recipe_run(recipe_run)
        assert job_id == json.loads(message)["job_id"]
    else:
        with pytest.raises(HTTPException):
            job_id_from_recipe_run(recipe_run)


@pytest.mark.parametrize(
    "gcloud_logging_response",
    ["Some logs returned by gcloud logging API"],
)
def test_get_logs(mocker, gcloud_logging_response):
    def mock_gcloud_logging_call(cmd: List[str]):
        return gcloud_logging_response

    mocker.patch.object(subprocess, "check_output", mock_gcloud_logging_call)

    logs = get_logs(
        job_id="2022-09-29_11_31_40-14379398480910960453",
        severity="ERROR",
        limit=1,
    )
    assert logs == gcloud_logging_response


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "get_logs_fixture",
    [
        dict(
            message='{"job_id": "abc"}',
            feedstock_spec="pangeo-forge/staged-recipes",
            commit="35d889f7c89e9f0d72353a0649ed1cd8da04826b",
            recipe_id="liveocean",
            gcloud_logging_response="Some logging message from gcloud API.",
            status="completed",
            conclusion="failure",
        ),
    ],
    indirect=True,
)
async def test_get_logs_via_recipe_run_id(
    mocker,
    get_logs_fixture,
    async_app_client,
):
    admin_headers, gcloud_logging_response, *_ = get_logs_fixture

    def mock_gcloud_logging_call(cmd: List[str]):
        return gcloud_logging_response

    mocker.patch.object(subprocess, "check_output", mock_gcloud_logging_call)

    response = await async_app_client.get(
        "/recipe_runs/1/logs",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.text == gcloud_logging_response


trace_tests_base_params = dict(
    message='{"job_id": "abc"}',
    feedstock_spec="pangeo-forge/staged-recipes",
    commit="35d889f7c89e9f0d72353a0649ed1cd8da04826b",
    recipe_id="liveocean",
    gcloud_logging_response=dedent(
        """
    Traceback
        a b c error
    Traceback
        e f g error
    """
    ),
)
trace_tests_params = [
    trace_tests_base_params | dict(status="completed", conclusion="failure"),
    trace_tests_base_params | dict(status="in_progress", conclusion=None),
    trace_tests_base_params | dict(status="queued", conclusion=None),
    trace_tests_base_params | dict(status="completed", conclusion="success"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("get_logs_fixture", trace_tests_params, indirect=True)
async def test_get_trace_via_recipe_run_id(
    mocker,
    get_logs_fixture,
    async_app_client,
):
    _, gcloud_logging_response, *_ = get_logs_fixture

    def mock_gcloud_logging_call(cmd: List[str]):
        return gcloud_logging_response

    mocker.patch.object(subprocess, "check_output", mock_gcloud_logging_call)

    recipe_run = await async_app_client.get("/recipe_runs/1")
    trace_response = await async_app_client.get("/recipe_runs/1/logs/trace")
    if recipe_run.json()["status"] == "completed" and recipe_run.json()["conclusion"] == "failure":
        assert trace_response.status_code == 200
        assert trace_response.text == "Traceback\n    e f g error\n"
    else:
        assert trace_response.status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "get_logs_fixture",
    [
        dict(
            message='{"job_id": "abc"}',
            feedstock_spec="pangeo-forge/staged-recipes",
            commit="35d889f7c89e9f0d72353a0649ed1cd8da04826b",
            recipe_id="liveocean",
            gcloud_logging_response="Some logging message from gcloud API.",
            status="completed",
            conclusion="failure",
        ),
    ],
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
        return gcloud_logging_response

    mocker.patch.object(subprocess, "check_output", mock_gcloud_logging_call)

    response = await async_app_client.get(
        f"/feedstocks/{feedstock_spec}/{commit}/{recipe_id}/logs",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.text == gcloud_logging_response


@pytest.mark.asyncio
@pytest.mark.parametrize("get_logs_fixture", trace_tests_params, indirect=True)
async def test_get_trace_human_readable_method(
    mocker,
    get_logs_fixture,
    async_app_client,
):
    (
        _,
        gcloud_logging_response,
        feedstock_spec,
        commit,
        recipe_id,
    ) = get_logs_fixture

    def mock_gcloud_logging_call(cmd: List[str]):
        return gcloud_logging_response

    mocker.patch.object(subprocess, "check_output", mock_gcloud_logging_call)

    recipe_run = await async_app_client.get("recipe_runs/1")
    trace_response = await async_app_client.get(
        f"/feedstocks/{feedstock_spec}/{commit}/{recipe_id}/logs/trace",
    )
    if recipe_run.json()["status"] == "completed" and recipe_run.json()["conclusion"] == "failure":
        assert trace_response.status_code == 200
        assert trace_response.text == "Traceback\n    e f g error\n"
    else:
        assert trace_response.status_code == 204
