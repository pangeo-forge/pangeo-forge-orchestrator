"""This module contains code adapted from https://github.com/Mariatta/gh_app_demo, a repo authored
by Mariatta Wijaya and licensed under Apache 2.0.
"""

import hashlib
import hmac
import json
import os
import subprocess
import time
from datetime import datetime
from textwrap import dedent

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
from sqlmodel import Session, select

from ..dependencies import get_session
from ..http import HttpSession, http_session
from ..logging import logger
from ..models import MODELS

# For now, we only have one app, installed in one place (the `pangeo-forge` org), so these are
# constants. Eventually, we'll have multiple apps (`staging`, etc.) installed in potentially
# multiple locations (> 1 account), at which point these will need to be determined dynamically.
# https://docs.github.com/en/rest/apps/apps#list-installations-for-the-authenticated-app
GH_APP_ID = 222382
INSTALLATION_ID = 27724604
ACCEPT = "application/vnd.github+json"

github_app_router = APIRouter()


def get_github_session(http_session: HttpSession):
    return GitHubAPI(http_session, "pangeo-forge")


def html_to_api_url(html_url: str) -> str:
    return html_url.replace("github.com", "api.github.com/repos")


def html_url_to_repo_full_name(html_url: str) -> str:
    return html_url.replace("https://github.com/", "")


def get_jwt():
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": GH_APP_ID,
    }
    bearer_token = jwt.encode(payload, os.getenv("PEM_FILE"), algorithm="RS256")

    return bearer_token


async def get_access_token(gh: GitHubAPI):
    token_response = await get_installation_access_token(
        gh,
        installation_id=INSTALLATION_ID,
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


@github_app_router.get(
    "/feedstocks/{id}/deliveries",
    summary="Get a list of webhook deliveries originating from a particular feedstock.",
)
async def get_feedstock_hook_deliveries(
    id: int,
    db_session: Session = Depends(get_session),
    http_session: HttpSession = Depends(http_session),
):

    feedstock = db_session.get(MODELS["feedstock"].table, id)
    if not feedstock:
        raise HTTPException(status_code=404, detail=f"Id {id} not found in feedstock table.")

    gh = get_github_session(http_session)
    accessible_repos = await list_accessible_repos(gh)

    if feedstock.spec in accessible_repos:
        repo_id = await get_repo_id(repo_full_name=feedstock.spec, gh=gh)
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Pangeo Forge GitHub App not installed in '{feedstock.spec}' repository.",
        )

    deliveries = []
    async for d in gh.getiter("/app/hook/deliveries", jwt=get_jwt(), accept=ACCEPT):
        if d["repository_id"] == repo_id:
            deliveries.append(d)

    return deliveries


@github_app_router.post(
    "/github/hooks/",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Endpoint to which Pangeo Forge GitHub App posts payloads.",
)
async def receive_github_hook(
    request: Request,
    background_tasks: BackgroundTasks,
    http_session: HttpSession = Depends(http_session),
    db_session: Session = Depends(get_session),
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

    gh = get_github_session(http_session)

    async def synchronize(html_url, head_sha, gh=gh):
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
        # TODO: make sure that `expand-meta` command verifies if python objects in recipe module
        # for each recipe in meta.yaml (i.e., that meta.yaml doesn't contain "null pointers").
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
        # TODO: create recipe runs in database for each recipe in expanded meta
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
        for nm in new_models:
            db_model = MODELS["recipe_run"].table.from_orm(nm)
            db_session.add(db_model)
            db_session.commit()
            db_session.refresh(db_model)
        # TODO: post notification back to github with created recipe runs
        update_request = dict(
            status="completed",
            conclusion="success",
            completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
            output=dict(
                title="Recipe runs queued for latest commit",
                summary=dedent(
                    """\
                    TODO: Links to recipe runs (requires knowing deployment base url)
                    """
                ),
            ),
        )
        _ = await update_check_run(gh, api_url, checks_response["id"], update_request)

    payload = await request.json()
    if payload["action"] == "synchronize":
        pr = payload["pull_request"]
        args = (pr["base"]["repo"]["html_url"], pr["head"]["sha"])
        background_tasks.add_task(synchronize, *args)
        return {"status": "ok", "background_tasks": [{"task": "synchronize", "args": args}]}
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="No handling implemented for this event type.",
        )


@github_app_router.get(
    "/github/hooks/deliveries",
    summary="Get all webhook deliveries, not filtered by originating feedstock repo.",
)
async def get_deliveries(http_session: HttpSession = Depends(http_session)):
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
    http_session: HttpSession = Depends(http_session),
):
    gh = get_github_session(http_session)
    delivery = await gh.getitem(f"/app/hook/deliveries/{id}", jwt=get_jwt(), accept=ACCEPT)
    return delivery["response"] if response_only else delivery
