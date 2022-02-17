import os

import aiohttp
import gidgethub.aiohttp
from fastapi import APIRouter, Depends

from ..dependencies import check_authentication_header

# TODO: this module is untested!
# We have deliberately accepted this techincal debt in order to get metrics up working quickly.
# Once we have some time for maintainance, we need to write tests for these endpoints.

OAUTH_TOKEN = os.environ["GITHUB_TOKEN"]
REQUESTER = "pangeo-forge-orchestrator"
REGISTRAR_DISPATCH_PATH = "/repos/pangeo-forge/registrar/dispatches"

_session = None


async def get_session():
    global _session
    if _session is None:
        _session = aiohttp.ClientSession()
    return _session


prefect_router = APIRouter()


@prefect_router.post(
    "/recipe_runs/register/{id}",
    summary="Register a recipe run as a Prefect Flow with Prefect Cloud.",
    tags=["recipe_run", "prefect", "admin"],
)
async def register_recipe_flow(id: int, authorized_user=Depends(check_authentication_header)):
    session = await get_session()

    # TODO: Input validation, e.g. make sure `id` is in database, and has appropriate status.
    # For example, recipe runs with status "completed" should not be allowed to be re-registered.

    gh = gidgethub.aiohttp.GitHubAPI(session, REQUESTER, oauth_token=OAUTH_TOKEN)
    dispatch_data = dict(
        event_type="register-flow",
        client_payload={
            "recipe_run_primary_key": id,
            "pangeo_forge_api_url": os.environ["PANGEO_FORGE_API_URL"],
        },
    )
    await gh.post(REGISTRAR_DISPATCH_PATH, data=dispatch_data)
