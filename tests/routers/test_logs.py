import json
import subprocess
from typing import List

import pytest
from fastapi import HTTPException

from pangeo_forge_orchestrator.models import MODELS
from pangeo_forge_orchestrator.routers.logs import get_logs, job_id_from_recipe_run


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
