"""This module contains code adapted from https://github.com/Mariatta/gh_app_demo, a repo authored
by Mariatta Wijaya and licensed under Apache 2.0.
"""

import os
import time

import aiohttp
import jwt
from fastapi import APIRouter, Depends
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
from sqlmodel import Session

from ..dependencies import get_session

GH_APP_ID = 222382
# For now, we're only installed in the `pangeo-forge` org, so this is a constant.
# https://docs.github.com/en/rest/apps/apps#list-installations-for-the-authenticated-app
INSTALLATION_ID = 27724604
ACCEPT = "application/vnd.github+json"

github_app_router = APIRouter()


def get_jwt():
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": GH_APP_ID,
    }
    bearer_token = jwt.encode(payload, os.getenv("PEM_FILE"), algorithm="RS256")

    return bearer_token


async def get_access_token():
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "pangeo-forge")
        token_response = await get_installation_access_token(
            gh,
            installation_id=INSTALLATION_ID,
            app_id=GH_APP_ID,
            private_key=os.getenv("PEM_FILE"),
        )
    return token_response["token"]


async def get_repo_id(repo_full_name: str):
    token = await get_access_token()
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "pangeo-forge")

        repo_response = await gh.getitem(
            f"/repos/{repo_full_name}",
            oauth_token=token,
            accept=ACCEPT,
        )
        return repo_response["id"]


@github_app_router.get(
    "/feedstocks/{id}/deliveries",
    summary="",
)
async def get_feedstock_hook_deliveries(id: int, session: Session = Depends(get_session)):

    repo_full_name = "pangeo-forge/github-app-sandbox-repository"
    repo_id = await get_repo_id(repo_full_name)

    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "pangeo-forge")

        deliveries = []
        async for d in gh.getiter("/app/hook/deliveries", jwt=get_jwt(), accept=ACCEPT):
            if d["repository_id"] == repo_id:
                deliveries.append(d)

        return deliveries
