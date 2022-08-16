import hashlib
import hmac
import json
import os
import subprocess
import time
from datetime import datetime
from textwrap import dedent
from typing import List
from urllib.parse import urlparse

import aiohttp
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
from sqlalchemy import and_
from sqlmodel import Session, select

from ..dependencies import get_session as get_database_session
from ..http import http_session
from ..logging import logger
from ..models import MODELS

GH_APP_ID = 222382
ACCEPT = "application/vnd.github+json"
FRONTEND_DASHBOARD_URL = "https://pangeo-forge.org/dashboard"
DEFAULT_BACKEND_NETLOC = "api.pangeo-forge.org"

github_app_router = APIRouter()


# Helpers -----------------------------------------------------------------------------------------


def get_github_session(http_session: aiohttp.ClientSession):
    return GitHubAPI(http_session, "pangeo-forge")


def html_to_api_url(html_url: str) -> str:
    return html_url.replace("github.com", "api.github.com/repos")


def html_url_to_repo_full_name(html_url: str) -> str:
    return html_url.replace("https://github.com/", "")


def get_jwt():
    """Adapted from https://github.com/Mariatta/gh_app_demo"""

    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": GH_APP_ID,
    }
    bearer_token = jwt.encode(payload, os.getenv("PEM_FILE"), algorithm="RS256")

    return bearer_token


async def get_access_token(gh: GitHubAPI):
    async for installation in gh.getiter("/app/installations", jwt=get_jwt(), accept=ACCEPT):
        installation_id = installation["id"]
        # I think installations are one per organization, so as long as we are only working with
        # repositories within the `pangeo-forge` organization, there should only ever be one
        # ``installation_id``. This assumption would change if we allow installations on accounts
        # other than the ``pangeo-forge`` org.
        break
    token_response = await get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=GH_APP_ID,
        private_key=os.getenv("PEM_FILE"),
    )
    return token_response["token"]


async def get_app_webhook_url(gh: GitHubAPI):
    response = await gh.getitem("/app/hook/config", jwt=get_jwt(), accept=ACCEPT)
    return response["url"]


async def create_check_run(gh: GitHubAPI, api_url: str, data: dict):
    token = await get_access_token(gh)
    kw = dict(oauth_token=token, accept=ACCEPT, data=data)
    response = await gh.post(f"{api_url}/check-runs", **kw)
    return response


async def update_check_run(gh: GitHubAPI, api_url: str, id_: str, data: dict):
    token = await get_access_token(gh)
    kw = dict(oauth_token=token, accept=ACCEPT, data=data)
    response = await gh.patch(f"{api_url}/check-runs/{id_}", **kw)
    return response


async def get_repo_id(repo_full_name: str, gh: GitHubAPI):
    token = await get_access_token(gh)
    repo_response = await gh.getitem(
        f"/repos/{repo_full_name}",
        oauth_token=token,
        accept=ACCEPT,
    )
    return repo_response["id"]


async def list_accessible_repos(gh: GitHubAPI):
    """Get all repos accessible to the GitHub App installation."""

    token = await get_access_token(gh)
    repo_response = await gh.getitem(
        "/installation/repositories",
        oauth_token=token,
        accept=ACCEPT,
    )
    return [r["full_name"] for r in repo_response["repositories"]]


async def repo_id_and_spec_from_feedstock_id(id: int, gh: GitHubAPI, db_session: Session):
    """Given a feedstock id, return the corresponding GitHub repo id and feedstock spec.

    In the process, confirm that the feedstock exists in the database and verify that the Pangeo
    Forge GitHub App is installed in the corresponding GitHub repo. Routes that query GitHub App
    details (e.g. ``/feedstocks/{id}/deliveries``, ``/feedstocks/{id}/{commit_sha}/check-runs``)
    will error if either of these conditions is not met.

    :param id: The feedstock's id in the Pangeo Forge database.
    """

    feedstock = db_session.get(MODELS["feedstock"].table, id)
    if not feedstock:
        raise HTTPException(status_code=404, detail=f"Id {id} not found in feedstock table.")

    accessible_repos = await list_accessible_repos(gh)

    if feedstock.spec in accessible_repos:
        repo_id = await get_repo_id(repo_full_name=feedstock.spec, gh=gh)
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Pangeo Forge GitHub App not installed in '{feedstock.spec}' repository.",
        )
    return repo_id, feedstock.spec


async def pass_if_deployment_not_selected(pr_labels: List[str], gh: aiohttp.ClientSession):
    """The specific deployment identifier should follow "only-backend-".

    There are three types of specific deployments:
      1. A persistent Heroku deployment (i.e. production, staging, etc.)
      2. An ephemeral Heroku deployment (e.g, a review app linked to a PR)
      3. A tunnel (i.e. smee channel) to a local dev server, as recommended in:
         https://docs.github.com/en/github-ae@latest/developers/apps/getting-started-with-apps/setting-up-your-development-environment-to-create-a-github-app
    """
    # TODO: THIS WONT WORK W/OUT GENERALIZING ``GH_APP_ID`` & ``INSTALLATION_ID`` CONSTANTS

    specific_deployments = [label for label in pr_labels if label.startswith("only-backend-")]
    if specific_deployments:
        app_webhook_url = await get_app_webhook_url(gh)
        for sd in specific_deployments:
            sd_identifier = sd.replace("only-backend-", "")
            if sd_identifier not in app_webhook_url:
                return {
                    "status": "pass",
                    "message": (
                        f"This deployment receives webhooks from {app_webhook_url}, which is "
                        f"not identified in the label set {specific_deployments}."
                    ),
                }
    return {"status": "ok"}


# Routes ------------------------------------------------------------------------------------------


@github_app_router.get(
    "/feedstocks/{id}/deliveries",
    summary="Get a list of webhook deliveries originating from a particular feedstock.",
)
async def get_feedstock_hook_deliveries(
    id: int,
    db_session: Session = Depends(get_database_session),
    http_session: aiohttp.ClientSession = Depends(http_session),
):
    gh = get_github_session(http_session)
    repo_id, _ = await repo_id_and_spec_from_feedstock_id(id, gh, db_session)
    deliveries = []
    async for d in gh.getiter("/app/hook/deliveries", jwt=get_jwt(), accept=ACCEPT):
        if d["repository_id"] == repo_id:
            deliveries.append(d)

    return deliveries


@github_app_router.get(
    "/feedstocks/{id}/commits/{commit_sha}/check-runs",
    summary="Get a list of check runs for a given commit sha on a feedstock.",
)
async def get_feedstock_check_runs(
    id: int,
    commit_sha: str,
    db_session: Session = Depends(get_database_session),
    http_session: aiohttp.ClientSession = Depends(http_session),
):
    gh = get_github_session(http_session)
    _, feedstock_spec = await repo_id_and_spec_from_feedstock_id(id, gh, db_session)

    token = await get_access_token(gh)
    check_runs = await gh.getitem(
        f"/repos/{feedstock_spec}/commits/{commit_sha}/check-runs",
        accept=ACCEPT,
        oauth_token=token,
    )
    return check_runs


@github_app_router.post(
    "/github/hooks/",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Endpoint to which Pangeo Forge GitHub App posts payloads.",
)
async def receive_github_hook(
    request: Request,
    background_tasks: BackgroundTasks,
    http_session: aiohttp.ClientSession = Depends(http_session),
    db_session: Session = Depends(get_database_session),
):
    # Hash signature validation documentation:
    # https://docs.github.com/en/developers/webhooks-and-events/webhooks/securing-your-webhooks#validating-payloads-from-github

    hash_signature = request.headers.get("X-Hub-Signature-256", None)
    if not hash_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request does not include a GitHub hash signature header.",
        )

    payload_bytes = await request.body()
    webhook_secret = bytes(os.environ["GITHUB_WEBHOOK_SECRET"], encoding="utf-8")  # type: ignore
    h = hmac.new(webhook_secret, payload_bytes, hashlib.sha256)
    if not hmac.compare_digest(hash_signature, f"sha256={h.hexdigest()}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Request hash signature invalid."
        )

    # NOTE: Background task functions cannot use FastAPI's Depends to resolve session
    # dependencies. We can resolve these dependencies (i.e., github session, database session)
    # here in the route function and then pass them through to the background task as kwargs.
    # See: https://github.com/tiangolo/fastapi/issues/4956#issuecomment-1140313872.
    gh = get_github_session(http_session)
    session_kws = dict(gh=gh, db_session=db_session)

    event = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    if event == "pull_request" and payload["action"] == "synchronize":
        pr = payload["pull_request"]

        maybe_pass = await pass_if_deployment_not_selected(pr["labels"], gh=gh)
        if maybe_pass["status"] == "pass":
            return maybe_pass

        args = (pr["base"]["repo"]["html_url"], pr["head"]["sha"])
        background_tasks.add_task(synchronize, *args, **session_kws)
        return {"status": "ok", "background_tasks": [{"task": "synchronize", "args": args}]}

    elif event == "issue_comment" and payload["action"] == "created":
        comment = payload["comment"]
        comment_body = comment["body"]
        reactions_url = comment["reactions"]["url"]

        token = await get_access_token(gh)
        gh_kws = dict(oauth_token=token, accept=ACCEPT)
        pr_response = await gh.getitem(payload["issue"]["pull_request"]["url"], **gh_kws)
        pr = pr_response.json()

        maybe_pass = await pass_if_deployment_not_selected(pr["labels"], gh=gh)
        if maybe_pass["status"] == "pass":
            return maybe_pass

        if not comment_body.startswith("/"):
            # Exit early if this isn't a slash command, so we don't end up spamming *every* issue
            # comment with automated emoji reactions.
            return {"status": "ok", "message": "Comment is not a slash command."}

        # Now that we know this is a slash command, posting the `eyes` reaction confirms to the user
        # that the command was received, mimicing the slash command dispatch github action UX.
        _ = await gh.post(reactions_url, data={"content": "eyes"}, **gh_kws)

        # So, what kind of slash command is this?
        cmd, *cmd_args = comment_body.split()
        if cmd == "/run":
            if len(cmd_args) != 1:
                detail = f"Command {cmd} not of form " "``['/run', RECIPE_NAME]``."
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
                # TODO: Maybe post a comment and/or emoji reaction explaining this error.
            recipe_id = cmd_args.pop(0)
            statement = and_(
                MODELS["recipe_run"].table.recipe_id == recipe_id,
                MODELS["recipe_run"].table.head_sha == pr["head"]["sha"],
            )
            result = db_session.query(MODELS["recipe_run"].table).filter(statement)
            logger.debug(result)
            # args = ()
            # background_tasks.add_task(run_recipe_test)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No handling implemented for this event type.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="No handling implemented for this event type.",
        )


@github_app_router.get(
    "/github/hooks/deliveries",
    summary="Get all webhook deliveries, not filtered by originating feedstock repo.",
)
async def get_deliveries(http_session: aiohttp.ClientSession = Depends(http_session)):
    gh = get_github_session(http_session)

    deliveries = []
    async for d in gh.getiter("/app/hook/deliveries", jwt=get_jwt(), accept=ACCEPT):
        deliveries.append(d)

    return deliveries


@github_app_router.get(
    "/github/hooks/deliveries/{id}",
    summary="Get details about a particular webhook delivery.",
)
async def get_delivery(
    id: int,
    response_only: bool = Query(True, description="Return only response body, excluding request."),
    http_session: aiohttp.ClientSession = Depends(http_session),
):
    gh = get_github_session(http_session)
    delivery = await gh.getitem(f"/app/hook/deliveries/{id}", jwt=get_jwt(), accept=ACCEPT)
    return delivery["response"] if response_only else delivery


# Background tasks --------------------------------------------------------------------------------


async def synchronize(html_url: str, head_sha: str, *, gh: GitHubAPI, db_session: Session):
    logger.info(f"Synchronizing {html_url} at {head_sha}.")
    api_url = html_to_api_url(html_url)
    create_request = dict(
        name="synchronize",
        head_sha=head_sha,
        status="in_progress",
        started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        output=dict(
            title="Syncing latest commit to Pangeo Forge Cloud",
            summary="",  # required
        ),
        details_url="https://pangeo-forge.org/",  # TODO: make this more specific.
    )
    checks_response = await create_check_run(gh, api_url, create_request)
    # TODO: add upstream `pangeo-forge-runner get-image` command, which only grabs the spec'd
    # image from meta.yaml, without importing the recipe. this will be used when we replace
    # subprocess calls with `docker.exec`, to pull & start the appropriate docker container.
    # TODO: make sure that `expand-meta` command verifies if python objects in recipe module exist
    # for each recipe in meta.yaml (i.e., that meta.yaml doesn't contain "null recipe pointers").
    # TODO: Also have pangeo-forge-runner raise descriptive effor for structure errors in the PR
    # (i.e., incorrect directory structure), and translate that here to failed check run.
    cmd = [
        "pangeo-forge-runner",
        "expand-meta",
        "--repo",
        html_url,
        "--ref",
        head_sha,
        "--json",
    ]
    out = subprocess.check_output(cmd)
    for line in out.splitlines():
        p = json.loads(line)
        if p["status"] == "completed":
            meta = p["meta"]
    logger.debug(meta)

    try:
        feedstock_statement = select(MODELS["feedstock"].table).where(
            MODELS["feedstock"].table.spec == html_url_to_repo_full_name(html_url)
        )
        feedstock_id = [result.id for result in db_session.exec(feedstock_statement)].pop(0)
        bakery_statement = select(MODELS["bakery"].table).where(
            MODELS["bakery"].table.name == meta["bakery"]["id"]
        )
        bakery_id = [result.id for result in db_session.exec(bakery_statement)].pop(0)
    except IndexError as e:
        update_request = dict(
            status="completed",
            conclusion="failure",
            completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
            output=dict(
                title="Feedstock and/or bakery not present in database.",
                summary=dedent(
                    f"""\
                    To resolve, a maintainer must ensure both of the following are in database:
                    - **Feedstock**: {html_url}
                    - **Bakery**: `{meta["bakery"]["id"]}`
                    """
                ),
            ),
        )
        _ = await update_check_run(gh, api_url, checks_response["id"], update_request)
        raise ValueError(
            f"Feedstock {html_url} and/or bakery {meta['bakery']['id']} not in database."
        ) from e

    new_models = [
        MODELS["recipe_run"].creation(
            recipe_id=recipe["id"],
            bakery_id=bakery_id,
            feedstock_id=feedstock_id,
            head_sha=head_sha,
            version="",  # TODO: Are we using this?
            started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
            is_test=True,
            # TODO: Derive `dataset_type` from recipe instance itself; hardcoding for now.
            # See https://github.com/pangeo-forge/pangeo-forge-recipes/issues/268
            # and https://github.com/pangeo-forge/staged-recipes/pull/154#issuecomment-1190925126
            dataset_type="zarr",
        )
        for recipe in meta["recipes"]
    ]
    created = []
    for nm in new_models:
        db_model = MODELS["recipe_run"].table.from_orm(nm)
        db_session.add(db_model)
        db_session.commit()
        db_session.refresh(db_model)
        created.append(db_model)
    summary = f"Recipe runs created at commit `{head_sha}`:"
    backend_app_webhook_url = await get_app_webhook_url(gh)
    backend_netloc = urlparse(backend_app_webhook_url).netloc
    query_param = (
        ""
        if backend_netloc == DEFAULT_BACKEND_NETLOC
        else f"?orchestratorEndpoint={backend_netloc}"
    )
    for model in created:
        summary += f"\n- {FRONTEND_DASHBOARD_URL}/recipe-run/{model.id}{query_param}"
    update_request = dict(
        status="completed",
        conclusion="success",
        completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        output=dict(title="Recipe runs queued for latest commit", summary=summary),
    )
    _ = await update_check_run(gh, api_url, checks_response["id"], update_request)


async def run_recipe_test(
    comment_body: str,
    reactions_url: str,
    *,
    gh: GitHubAPI,
    db_session: Session,
):
    """ """
    pass
