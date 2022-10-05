import json
import subprocess
import tempfile
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, SecretStr
from sqlmodel import Session, SQLModel, select
from starlette import status

from ..config import get_config
from ..dependencies import get_session as get_database_session
from ..models import MODELS

logs_router = APIRouter()

DEFAULT_SOURCE = Query(
    "worker",
    description=(
        "A valid dataflow logging source. Must be one of: ['kubelet', 'shuffler', 'harness', "
        "'harness-startup', 'vm-health', 'vm-monitor', 'resource', 'agent', 'docker', 'system', "
        "'shuffler-startup', 'worker']"
    ),
)
DEFAULT_SEVERITY = Query(
    "ERROR",
    description=(
        "A valid gcloud logging severity as defined in "
        "https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#LogSeverity"
    ),
)
DEFAULT_LIMIT = Query(1, description="Max number of log entries to return.")


def job_name_from_recipe_run(recipe_run: SQLModel) -> str:
    try:
        job_name = json.loads(recipe_run.message)["job_name"]
    except (KeyError, json.JSONDecodeError) as e:
        detail = (
            f"Message field of {recipe_run = } missing 'job_name'."
            if type(e) == KeyError
            else f"Message field of {recipe_run = } not JSON decodable."
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    return job_name


def secret_str_vals_from_basemodel(model: BaseModel) -> List[str]:
    """From a pydantic BaseModel, recursively surface all fields with type SecretStr."""

    # this list must be defined outside the recursive `surface_secrets` function,
    # or else it will be re-assigned to empty when the function recurses
    secret_str_vals = []

    def is_pydantic_model(obj):
        return isinstance(obj, BaseModel)

    def surface_secrets(model: BaseModel):
        if is_pydantic_model(model):
            for var in vars(model):
                if is_pydantic_model(getattr(model, var)):
                    surface_secrets(getattr(model, var))
                elif isinstance(getattr(model, var), SecretStr):
                    secret_str_vals.append(json.loads(model.json())[var])
        else:
            pass

    surface_secrets(model)
    return secret_str_vals


def get_logs(
    job_name: str,
    # TODO: add param `severity: str,`
    source: str,
    recipe_run: SQLModel,
    db_session: Session,
):
    cmd = [
        "python3",
        "./pangeo_forge_orchestrator/bakeries/dataflow/fetch_logs.py",
        job_name,
        f"--source={source}",
    ]
    logs = subprocess.check_output(cmd).decode("utf-8")

    # First security check: ensure known bakery secrets do not appear in logs
    statement = select(MODELS["bakery"].table).where(
        MODELS["bakery"].table.id == recipe_run.bakery_id
    )
    bakery = db_session.exec(statement).one()
    bakery_config = get_config().bakeries[bakery.name]
    bakery_secrets = secret_str_vals_from_basemodel(bakery_config)
    for secret in bakery_secrets:
        if secret in logs:
            raise ValueError("Bakery secret detected in logs.")

    # Second security check: gitleaks
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(f"{tmpdir}/c.json", mode="w") as f:
            json.dump(json.loads(logs), f)
            gitleaks_cmd = "gitleaks detect --no-git".split()
            gitleaks = subprocess.run(gitleaks_cmd, cwd=tmpdir)
            if not gitleaks.returncode == 0:
                raise ValueError("Gitleaks detected secrets in the logs.")

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
)
async def raw_logs_from_recipe_run_id(
    id: int,
    *,
    db_session: Session = Depends(get_database_session),
    source: str = DEFAULT_SOURCE,
    # severity: str = DEFAULT_SEVERITY,
    # limit: int = DEFAULT_LIMIT,
):
    recipe_run = recipe_run_from_id(id, db_session)
    job_name = job_name_from_recipe_run(recipe_run)
    raw_logs = get_logs(job_name, source, recipe_run, db_session)
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
)
async def raw_logs_from_feedstock_spec_commit_and_recipe_id(
    feedstock_spec: str,
    commit: str,
    recipe_id: str,
    *,
    db_session: Session = Depends(get_database_session),
    source: str = DEFAULT_SOURCE,
    # severity: str = DEFAULT_SEVERITY,
    # limit: int = DEFAULT_LIMIT,
):
    recipe_run = recipe_run_from_feedstock_spec_commit_and_recipe_id(
        feedstock_spec,
        commit,
        recipe_id,
        db_session,
    )
    job_name = job_name_from_recipe_run(recipe_run)
    raw_logs = get_logs(job_name, source, recipe_run, db_session)
    return raw_logs
