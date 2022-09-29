import subprocess

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from ..dependencies import check_authentication_header, get_session as get_database_session

logs_router = APIRouter()


def get_logs(
    job_id="2022-09-29_11_31_40-14379398480910960453",  # set from recipe_run
    severity="ERROR",  # set from query
    limit=1,  # set from query
):
    query = (
        'resource.type="dataflow_step" '
        f'AND resource.labels.job_id="{job_id}" '
        "AND logName=("
        '"projects/pangeo-forge-4967/logs/dataflow.googleapis.com%2Fjob-message" '
        'OR "projects/pangeo-forge-4967/logs/dataflow.googleapis.com%2Flauncher") '
        f'AND severity="{severity}"'
    )
    cmd = "gcloud logging read".split() + [query]

    if limit:
        cmd += [f"--limit={limit}"]

    print(cmd)
    logs = subprocess.check_output(cmd)

    return logs


@logs_router.get(
    "/recipe_runs/{id}/logs",
    summary="Get job logs for a recipe_run, specified by database id.",
    tags=["recipe_run", "logs", "admin"],
    response_class=PlainTextResponse,
    dependencies=[Depends(check_authentication_header)],
)
async def logs_from_recipe_run_id(
    id: int,
    db_session: Session = Depends(get_database_session),
):
    logs = get_logs()
    return logs


@logs_router.get(
    "/feedstocks/{org}/{repo}/{commit}/{recipe_id}/logs",
    summary="Get job logs for a recipe run, specified by feedstock_spec, commit, and recipe_id.",
    tags=["feedstock", "logs", "admin"],
    response_class=PlainTextResponse,
    dependencies=[Depends(check_authentication_header)],
)
async def logs_from_feedstock_spec_commit_and_recipe_id(
    org: str,
    repo: str,
    commit: str,
    recipe_id: str,
    db_session: Session = Depends(get_database_session),
):
    logs = get_logs()
    return logs
