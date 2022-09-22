"""Most of the GitHub App helpers are tested in test_helpers_misc.py
This module tests the `run` function, which is a special case.
"""

import subprocess

import pytest
import pytest_asyncio
from sqlmodel import Session

from pangeo_forge_orchestrator.database import engine
from pangeo_forge_orchestrator.http import http_session
from pangeo_forge_orchestrator.models import MODELS
from pangeo_forge_orchestrator.routers.github_app import run

from ..conftest import clear_database
from .fixtures import _MockGitHubBackend, get_mock_github_session
from .mock_pangeo_forge_runner import (
    mock_subprocess_check_output,
    mock_subprocess_check_output_raises_called_process_error,
)


@pytest_asyncio.fixture(
    params=[
        dict(
            feedstock_spec="pangeo-forge/staged-recipes",
            is_test=True,
            feedstock_subdir="gpcp",
        ),
    ],
)
async def run_fixture(
    admin_key,
    async_app_client,
    request,
):

    admin_headers = {"X-API-Key": admin_key}
    bakery_create_response = await async_app_client.post(
        "/bakeries/",
        json={  # TODO: set dynamically
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

    # In other tests, we setup the recipe_run table via
    #    ```
    #    recipe_run_response = await async_app_client.post("/feedstocks/", ...)
    #    ```
    # In those cases, we do not have to use the recipe run `SQLModel` object itself as an argument
    # to the test. Rather, we simply need the recipe_run to be queryable as JSON from the database.
    # In this test, we *do need* the `SQLModel` object, to pass to `run()`, and this seems to be a
    # (the only?) way to do that. In any case, this is how we create the object in the `github_app`
    # router itself, so even if there are other ways to do this, this is the most realistic:
    with Session(engine) as db_session:
        model = MODELS["recipe_run"].creation(
            **{
                "recipe_id": "eooffshore_ics_cmems_WIND",
                "bakery_id": 1,
                "feedstock_id": 1,
                "head_sha": "037542663cb7f7bc4a04777c90d85accbff01c8c",
                "version": "",
                "started_at": "2022-09-19T16:31:43",
                "completed_at": None,
                "conclusion": None,
                "status": "queued",
                "is_test": request.param["is_test"],
                "dataset_type": "zarr",
                "dataset_public_url": None,
                "message": None,
            },
        )
        db_model = MODELS["recipe_run"].table.from_orm(model)
        db_session.add(db_model)
        db_session.commit()
        db_session.refresh(db_model)

    gh_backend_kws = {}
    gh_backend = _MockGitHubBackend(**gh_backend_kws)
    mock_gh = get_mock_github_session(gh_backend)(http_session)

    with Session(engine) as db_session:
        run_kws = dict(
            html_url=f"{request.param['feedstock_spec']}",
            ref=db_model.head_sha,
            recipe_run=db_model,
            feedstock_spec=request.param["feedstock_spec"],
            feedstock_subdir=request.param["feedstock_subdir"],
            gh=mock_gh,
            db_session=db_session,
        )
        yield run_kws

    # database teardown
    clear_database()


@pytest.mark.asyncio
@pytest.mark.parametrize("raises_called_process_error", [True, False])
async def test_run(
    mocker,
    run_fixture,
    raises_called_process_error,
):
    run_kws = run_fixture

    if raises_called_process_error:
        mocker.patch.object(
            subprocess,
            "check_output",
            mock_subprocess_check_output_raises_called_process_error,
        )
        with pytest.raises(KeyError, match=r"status"):
            await run(**run_kws)
    else:
        mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)
        await run(**run_kws)
