import json

import pytest
from fastapi import HTTPException

from pangeo_forge_orchestrator.models import MODELS
from pangeo_forge_orchestrator.routers.logs import job_id_from_recipe_run


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
