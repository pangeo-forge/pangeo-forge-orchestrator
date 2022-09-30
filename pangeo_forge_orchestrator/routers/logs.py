import json
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, SQLModel, select
from starlette import status

from ..dependencies import check_authentication_header, get_session as get_database_session
from ..models import MODELS

logs_router = APIRouter()

DEFAULT_SEVERITY = Query(
    "ERROR",
    description=(
        "A valid gcloud logging severity as defined in "
        "https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#LogSeverity"
    ),
)
DEFAULT_LIMIT = Query(1, description="Max number of log entries to return.")


def job_id_from_recipe_run(recipe_run: SQLModel) -> str:
    try:
        job_id = json.loads(recipe_run.message)["job_id"]
    except (KeyError, json.JSONDecodeError) as e:
        detail = (
            f"Message field of {recipe_run = } missing 'job_id'."
            if type(e) == KeyError
            else f"Message field of {recipe_run = } not JSON decodable."
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    return job_id


def get_logs(
    job_id: str,
    severity: str,
    limit: int,
):
    log_name_prefix = "projects/pangeo-forge-4967/logs/dataflow.googleapis.com"
    query = (
        'resource.type="dataflow_step" '
        f'AND resource.labels.job_id="{job_id}" '
        f'AND logName=("{log_name_prefix}%2Fjob-message" OR "{log_name_prefix}%2Flauncher") '
        f'AND severity="{severity}"'
    )
    cmd = "gcloud logging read".split() + [query]

    if limit:
        cmd += [f"--limit={limit}"]

    logs = subprocess.check_output(cmd)
    return logs


def recipe_run_from_id(
    id: int,
    db_session: Session,
) -> SQLModel:
    recipe_run = db_session.exec(
        select(MODELS["recipe_run"].table).where(MODELS["recipe_run"].table.id == id)
    ).one()
    return recipe_run


@logs_router.get(
    "/recipe_runs/{id}/logs",
    summary="Get job logs for a recipe_run, specified by database id.",
    tags=["recipe_run", "logs", "admin"],
    response_class=PlainTextResponse,
    dependencies=[Depends(check_authentication_header)],
)
async def raw_logs_from_recipe_run_id(
    id: int,
    *,
    db_session: Session = Depends(get_database_session),
    severity: str = DEFAULT_SEVERITY,
    limit: int = DEFAULT_LIMIT,
):
    recipe_run = recipe_run_from_id(id, db_session)
    job_id = job_id_from_recipe_run(recipe_run)
    raw_logs = get_logs(job_id, severity, limit)
    return raw_logs


def recipe_run_from_feedstock_spec_commit_and_recipe_id(
    feedstock_spec: str,
    commit: str,
    recipe_id: str,
    db_session: Session,
) -> SQLModel:
    feedstock = db_session.exec(
        select(MODELS["feedstock"].table).where(MODELS["feedstock"].table.spec == feedstock_spec)
    ).one()
    statement = (
        select(MODELS["recipe_run"].table)
        .where(MODELS["recipe_run"].table.recipe_id == recipe_id)
        .where(MODELS["recipe_run"].table.head_sha == commit)
        .where(MODELS["recipe_run"].table.feedstock_id == feedstock.id)
    )
    recipe_run = db_session.exec(statement).one()
    return recipe_run


@logs_router.get(
    "/feedstocks/{feedstock_spec:path}/{commit}/{recipe_id}/logs",
    summary="Get job logs for a recipe run, specified by feedstock_spec, commit, and recipe_id.",
    tags=["feedstock", "logs", "admin"],
    response_class=PlainTextResponse,
    dependencies=[Depends(check_authentication_header)],
)
async def raw_logs_from_feedstock_spec_commit_and_recipe_id(
    feedstock_spec: str,
    commit: str,
    recipe_id: str,
    *,
    db_session: Session = Depends(get_database_session),
    severity: str = DEFAULT_SEVERITY,
    limit: int = DEFAULT_LIMIT,
):
    recipe_run = recipe_run_from_feedstock_spec_commit_and_recipe_id(
        feedstock_spec,
        commit,
        recipe_id,
        db_session,
    )
    job_id = job_id_from_recipe_run(recipe_run)
    raw_logs = get_logs(job_id, severity, limit)
    return raw_logs
