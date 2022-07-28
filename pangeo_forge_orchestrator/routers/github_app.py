"""This module contains code adapted from https://github.com/Mariatta/gh_app_demo, a repo authored
by Mariatta Wijaya and licensed under Apache 2.0.
"""

import hashlib
import hmac
import os
import time

import aiohttp
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
from sqlmodel import Session

from ..dependencies import get_session
from ..models import MODELS

# For now, we only have one app, installed in one place (the `pangeo-forge` org), so these are
# constants. Eventually, we'll have multiple apps (`staging`, etc.) installed in potentially
# multiple locations (> 1 account), at which point these will need to be determined dynamically.
# https://docs.github.com/en/rest/apps/apps#list-installations-for-the-authenticated-app
GH_APP_ID = 222382
INSTALLATION_ID = 27724604
ACCEPT = "application/vnd.github+json"

github_app_router = APIRouter()
# Based on https://github.com/tiangolo/fastapi/issues/236#issuecomment-493873907, it looks like
# starting a single global aiohttp session outside of a context manager is fine. Encouraged, even.
# We currently don't have a "close on shutdown" mechanism, but I'm not clear that's needed.
http_session = aiohttp.ClientSession()  # TODO: Maybe share this across all routers.
gh = GitHubAPI(http_session, "pangeo-forge")


def get_jwt():
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": GH_APP_ID,
    }
    bearer_token = jwt.encode(payload, os.getenv("PEM_FILE"), algorithm="RS256")

    return bearer_token


async def get_access_token():
    token_response = await get_installation_access_token(
        gh,
        installation_id=INSTALLATION_ID,
        app_id=GH_APP_ID,
        private_key=os.getenv("PEM_FILE"),
    )
    return token_response["token"]


async def get_repo_id(repo_full_name: str):
    token = await get_access_token()
    repo_response = await gh.getitem(
        f"/repos/{repo_full_name}",
        oauth_token=token,
        accept=ACCEPT,
    )
    return repo_response["id"]


async def list_accessible_repos():
    """Get all repos accessible to the GitHub App installation."""

    token = await get_access_token()
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
async def get_feedstock_hook_deliveries(id: int, db_session: Session = Depends(get_session)):

    feedstock = db_session.get(MODELS["feedstock"].table, id)
    if not feedstock:
        raise HTTPException(status_code=404, detail=f"Id {id} not found in feedstock table.")

    accessible_repos = await list_accessible_repos()
    if feedstock.spec in accessible_repos:
        repo_id = await get_repo_id(repo_full_name=feedstock.spec)
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
async def receive_github_hook(request: Request):
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
    if not hash_signature == f"sha256={h.hexdigest()}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Request hash signature invalid."
        )

    # payload_json = await request.json()
    # TODO: Custom response per payload type, will be useful for deliveries log.
    return {"status": "ok"}


@github_app_router.get(
    "/github/hooks/deliveries",
    summary="Get all webhook deliveries, not filtered by originating feedstock repo.",
)
async def get_deliveries():
    deliveries = []
    async for d in gh.getiter("/app/hook/deliveries", jwt=get_jwt(), accept=ACCEPT):
        deliveries.append(d)

    return deliveries


@github_app_router.get(
    "/github/hooks/deliveries/{id}",
    summary="Get details about a particular webhook delivery.",
)
async def get_delivery(id: int):
    return {"status": "ok"}
