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

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
from sqlmodel import Session

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
        token = await get_access_token(gh)
        checks_response = await gh.post(
            f"{api_url}/check-runs",
            oauth_token=token,
            accept=ACCEPT,
            data=dict(
                name="synchronize",
                head_sha=head_sha,
                status="in_progress",
                started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
                output=dict(
                    title="sync latest commit to pangeo forge cloud",
                    summary="",  # required
                    text="",  # required
                ),
                details_url="https://pangeo-forge.org/",  # TODO: make this more specific.
            ),
        )
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
        # TODO: post notification back to github with created recipe runs
        _ = await gh.patch(
            f"{api_url}/check-runs/{checks_response['id']}",
            oauth_token=token,
            accept=ACCEPT,
            data=dict(
                status="completed",
                conclusion="success",
                completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
            ),
        )

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
