import hashlib
import hmac
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from textwrap import dedent
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound
from sqlmodel import Session, SQLModel, select

from ..config import get_config
from ..dependencies import get_session as get_database_session
from ..http import http_session
from ..logging import logger
from ..models import MODELS

ACCEPT = "application/vnd.github+json"
FRONTEND_DASHBOARD_URL = "https://pangeo-forge.org/dashboard"
DEFAULT_BACKEND_NETLOC = "api.pangeo-forge.org"

github_app_router = APIRouter()


# Helpers -----------------------------------------------------------------------------------------


def ignore_repo(repo: str) -> bool:
    """Return True if the repo should be ignored."""

    return not repo.lower().endswith("-feedstock") and not repo.lower().endswith("staged-recipes")


def get_github_session(http_session: aiohttp.ClientSession):
    return GitHubAPI(http_session, "pangeo-forge")


def html_to_api_url(html_url: str) -> str:
    return html_url.replace("github.com", "api.github.com/repos")


def html_url_to_repo_full_name(html_url: str) -> str:
    return html_url.replace("https://github.com/", "")


def get_jwt() -> str:
    """Adapted from https://github.com/Mariatta/gh_app_demo"""

    github_app = get_config().github_app
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": github_app.id,
    }
    return jwt.encode(payload, github_app.private_key, algorithm="RS256")


async def get_access_token(gh: GitHubAPI) -> str:
    github_app = get_config().github_app
    async for installation in gh.getiter("/app/installations", jwt=get_jwt(), accept=ACCEPT):
        installation_id = installation["id"]
        # Even if installed on multiple repos within the account, I believe installations are
        # one per account (organization or user), so as long as apps are only ever deployed in
        # the account they were created in, there should only ever be one installation_id per app.
        # Currently, this assumption holds, because named deployments are made from private apps
        # owned by the pangeo-forge org, and only deployed in pangeo-forge, and dev apps are made
        # by developers, and only deployed in on repos they own. If we were to change this
        # paradigm, the assumption that the first installation returned by this `getiter` call is
        # the only installation (and therefore the one we want), would change.
        break
    token_response = await get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=github_app.id,
        private_key=github_app.private_key,
    )
    return token_response["token"]


async def get_app_webhook_url(gh: GitHubAPI) -> str:
    if heroku_app_name := os.environ.get("HEROKU_APP_NAME", None):
        # This env var is only set on Heroku Review Apps, so if it's present, we know
        # we need to generate the review app url here, because the GitHub App webhook
        # url is a proxy url, and not the actual url for this review app instance.
        return f"https://{heroku_app_name}.herokuapp.com/github/hooks/"
    else:
        # This is not a Review App, so we can query the GitHub App webhook url.
        response = await gh.getitem("/app/hook/config", jwt=get_jwt(), accept=ACCEPT)
        return response["url"]


async def get_repo_id(repo_full_name: str, gh: GitHubAPI) -> str:
    token = await get_access_token(gh)
    repo_response = await gh.getitem(
        f"/repos/{repo_full_name}",
        oauth_token=token,
        accept=ACCEPT,
    )
    return repo_response["id"]


async def list_accessible_repos(gh: GitHubAPI) -> list[str]:
    """Get all repos accessible to the GitHub App installation."""

    token = await get_access_token(gh)
    repo_response = await gh.getitem(
        "/installation/repositories",
        oauth_token=token,
        accept=ACCEPT,
    )
    return [r["full_name"] for r in repo_response["repositories"]]


async def repo_id_and_spec_from_feedstock_id(
    id: int, gh: GitHubAPI, db_session: Session
) -> tuple[str, str]:
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


async def maybe_specify_feedstock_subdir(
    api_url: str,
    pr_number: str,
    gh: GitHubAPI,
) -> Optional[str]:
    """If this is staged-recipes, add the --feedstock-subdir option to the command."""

    if "staged-recipes" in api_url:
        token = await get_access_token(gh)
        files = await gh.getitem(
            f"{api_url}/pulls/{pr_number}/files",
            oauth_token=token,
            accept=ACCEPT,
        )
        subdir = files[0]["filename"].split("/")[1]
        return f"recipes/{subdir}"

    return None


def get_storage_subpath_identifier(feedstock_spec: str, recipe_run: SQLModel):
    # TODO: Other storage locations may prefer a different layout, but this is how
    # we're solving this for OSN. Eventaully we could expose higher up in Traitlets
    # config of `pangeo-forge-runner`. The basic idea is that path should be determined
    # by a combindation of *deployment* (don't want staging app overwriting production data),
    # *is_test*, *feedstock.spec*, *recipe_run.id*, and *dataset_type* (i.e. file extension).
    # The traitlets config doesn't offer this much configurability in `root_path` right now,
    # so just doing this here for the moment.

    app_name = get_config().github_app.app_name
    if recipe_run.is_test:
        prefix = f"{app_name}/test/{feedstock_spec}/recipe-run-{recipe_run.id}"
    else:
        prefix = f"{app_name}/{feedstock_spec}"

    return f"{prefix}/{recipe_run.recipe_id}.{recipe_run.dataset_type}"


# Routes ------------------------------------------------------------------------------------------


@github_app_router.get(
    "/feedstocks/{id}/deliveries",
    summary="Get a list of webhook deliveries originating from a particular feedstock.",
    tags=["github_app", "feedstock", "public"],
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
    tags=["github_app", "feedstock", "public"],
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
    tags=["github_app", "admin"],
)
async def receive_github_hook(  # noqa: C901
    request: Request,
    background_tasks: BackgroundTasks,
    http_session: aiohttp.ClientSession = Depends(http_session),
    db_session: Session = Depends(get_database_session),
):
    # Hash signature validation documentation:
    # https://docs.github.com/en/developers/webhooks-and-events/webhooks/securing-your-webhooks#validating-payloads-from-github

    payload_bytes = await request.body()
    await verify_hash_signature(request, payload_bytes)

    # NOTE: Background task functions cannot use FastAPI's Depends to resolve session
    # dependencies. We can resolve these dependencies (i.e., github session, database session)
    # here in the route function and then pass them through to the background task as kwargs.
    # See: https://github.com/tiangolo/fastapi/issues/4956#issuecomment-1140313872.
    gh = get_github_session(http_session)
    session_kws = dict(gh=gh, db_session=db_session)
    token = await get_access_token(gh)
    gh_kws = dict(oauth_token=token, accept=ACCEPT)

    event = request.headers.get("X-GitHub-Event")
    payload = await parse_payload(request, payload_bytes, event)

    # TODO: maybe bring this back as a way to filter which PRs run on which apps.
    # With addition of `pforgetest` org, might not be necessary, however. TBD.
    # logger.info("Checking to see if PR has {label} label...")
    # if event in ["pull_request", "issue_comment"]:
    #    obj = payload[event] if event == "pull_request" else payload["issue"]
    #    if obj["labels"][0]["name"] != "{label}":
    #        logger.info("PR does not have {label} label, skipping")
    #        return {"message": "not a {label} pr, skipping"}
    #    logger.info("PR label found, continuing...")

    if event == "pull_request":
        return await handle_pr_event(
            payload=payload,
            background_tasks=background_tasks,
            session_kws=session_kws,
            gh=gh,
            gh_kws=gh_kws,
        )
    elif event == "issue_comment":
        return await handle_pr_comment_event(
            payload=payload,
            gh=gh,
            background_tasks=background_tasks,
            session_kws=session_kws,
            gh_kws=gh_kws,
            db_session=db_session,
        )
    elif event == "dataflow":
        return await handle_dataflow_event(
            payload=payload,
            db_session=db_session,
            background_tasks=background_tasks,
            gh_kws=gh_kws,
            gh=gh,
        )

    elif event == "check_suite":
        # We create check runs directly using the head_sha from the assocaited PR.
        # TBH, I'm not sure if/how it would be better to use this object, but we get a lot
        # of these requests from GitHub, so just conveying that we expect that here, for now.
        return {"status": "ok"}

    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="No handling implemented for this event type.",
        )


async def handle_dataflow_event(
    *,
    payload: dict,
    db_session: Session,
    background_tasks: BackgroundTasks,
    gh: GitHubAPI,
    gh_kws: dict,
):
    logger.info(f"Received dataflow webhook with {payload = }")

    action = payload["action"]

    if action == "completed":
        if payload["conclusion"] not in ("success", "failure"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No handling implemented for {payload['conclusion'] = }.",
            )

        recipe_run = db_session.exec(
            select(MODELS["recipe_run"].table).where(
                MODELS["recipe_run"].table.id == int(payload["recipe_run_id"])
            )
        ).one()
        feedstock = db_session.exec(
            select(MODELS["feedstock"].table).where(
                MODELS["feedstock"].table.id == recipe_run.feedstock_id
            )
        ).one()
        bakery = db_session.exec(
            select(MODELS["bakery"].table).where(MODELS["bakery"].table.id == recipe_run.bakery_id)
        ).one()

        recipe_run.status = "completed"
        recipe_run.conclusion = payload["conclusion"]
        recipe_run.completed_at = datetime.utcnow()

        if recipe_run.conclusion == "success":
            bakery_config = get_config().bakeries[bakery.name]
            subpath = get_storage_subpath_identifier(feedstock.spec, recipe_run)
            root_path = bakery_config.TargetStorage.root_path.format(subpath=subpath)
            recipe_run.dataset_public_url = bakery_config.TargetStorage.public_url.format(  # type: ignore
                root_path=root_path
            )
        db_session.add(recipe_run)
        db_session.commit()

        # Wow not every day you google a error and see a comment on it by Guido van Rossum
        # https://github.com/python/mypy/issues/1174#issuecomment-175854832
        args: list[SQLModel] = [recipe_run]  # type: ignore
        if recipe_run.is_test:
            args.append(feedstock.spec)  # type: ignore
            logger.info(f"Calling `triage_test_run_complete` with {args=}")
            background_tasks.add_task(triage_test_run_complete, *args, gh=gh, gh_kws=gh_kws)
        else:
            logger.info(f"Calling `triage_prod_run_complete` with {args=}")
            background_tasks.add_task(triage_prod_run_complete, *args, gh=gh, gh_kws=gh_kws)


async def handle_pr_comment_event(
    *,
    payload: dict,
    gh: GitHubAPI,
    gh_kws: dict,
    background_tasks: BackgroundTasks,
    session_kws: dict,
    db_session: Session,
):
    """Handle a pull request comment event.

    Parameters
    ----------
    payload : dict
        The payload from the GitHub webhook request.
    gh : GitHubAPI
        The authenticated GitHub API client.
    gh_kws : dict
        The keyword arguments to pass to the GitHub API client.
    background_tasks : BackgroundTasks
        The FastAPI background tasks object.
    session_kws : dict
        The keyword arguments to pass to the SQLAlchemy session.
    db_session : Session
        The SQLAlchemy session.

    """
    logger.info(f"Handling PR comment event with payload {payload=}")

    action = payload["action"]
    comment = payload["comment"]
    pr = await gh.getitem(payload["issue"]["pull_request"]["url"], **gh_kws)

    if action == "created":
        comment_body = comment["body"]
        if not comment_body.startswith("/"):
            # Exit early if this isn't a slash command, so we don't end up spamming *every* issue
            # comment with automated emoji reactions.
            return {"status": "ok", "message": "Comment is not a slash command."}

        reactions_url = comment["reactions"]["url"]

        # Now that we know this is a slash command, posting the `eyes` reaction confirms to the user
        # that the command was received, mimicing the slash command dispatch github action UX.
        _ = await gh.post(reactions_url, data={"content": "eyes"}, **gh_kws)

        # So, what kind of slash command is this?
        cmd, *cmd_args = comment_body.split()
        if cmd != "/run":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No handling implemented for this event type.",
            )

        if len(cmd_args) != 1:
            detail = f"Command {cmd} not of form " "``['/run', RECIPE_NAME]``."
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
            # TODO: Maybe post a comment and/or emoji reaction explaining this error.
        recipe_id = cmd_args.pop(0)
        statement = (
            # https://sqlmodel.tiangolo.com/tutorial/where/#multiple-where
            select(MODELS["recipe_run"].table)
            .where(MODELS["recipe_run"].table.recipe_id == recipe_id)
            .where(MODELS["recipe_run"].table.head_sha == pr["head"]["sha"])
        )
        # TODO: handle error if there is no matching result. this would arise if the slash
        # command arg was a recipe_id that doesn't exist for this feedstock + head_sha combo.
        matching_recipe_run = db_session.exec(statement).one()
        logger.debug(matching_recipe_run)
        args = (  # type: ignore
            pr["head"]["repo"]["html_url"],
            pr["base"]["repo"]["url"],
            pr["head"]["sha"],
            pr["number"],
            matching_recipe_run,
            pr["base"]["repo"]["full_name"],
            reactions_url,
        )
        logger.info(f"Creating run_recipe_test task with args: {args}")
        background_tasks.add_task(run_recipe_test, *args, **session_kws, gh_kws=gh_kws)


async def handle_pr_event(
    *,
    payload: dict,
    gh_kws: dict[str, Any],
    gh: GitHubAPI,
    session_kws: dict[str, Any],
    background_tasks: BackgroundTasks,
):
    """Process a PR event."""

    logger.info(f"Handling PR event with payload {payload=}")

    action = payload["action"]
    pr = payload["pull_request"]

    if action in ("synchronize", "opened"):
        base_repo_name = pr["base"]["repo"]["full_name"]
        if ignore_repo(base_repo_name):
            return {"status": "ok", "message": f"Skipping synchronize for repo {base_repo_name}"}
        if pr["title"].lower().startswith("cleanup"):
            return {"status": "skip", "message": "This is an automated cleanup PR. Skipping."}
        args = (
            pr["head"]["repo"]["html_url"],
            pr["head"]["sha"],
            pr["number"],
            pr["base"]["repo"]["url"],
            pr["base"]["repo"]["full_name"],
        )
        background_tasks.add_task(synchronize, *args, **session_kws, gh_kws=gh_kws)
        return {"status": "ok", "background_tasks": [{"task": "synchronize", "args": args}]}

    elif action == "closed" and pr["merged"]:
        logger.info("Received PR merged event...")

        files_changed = await gh.getitem(
            f"{pr['base']['repo']['url']}/pulls/{pr['number']}/files",
            **gh_kws,
        )
        # TODO[**IMPORTANT**]: make sure that `synchronize` task fails check run if
        # PRs attempt to mix recipe + config changes, and that this failure is somehow
        # connected to a branch protection rule for feedstocks + staged-recipes.
        # See: https://github.com/pangeo-forge/pangeo-forge-orchestrator/issues/109
        # If we get to this stage (pr merged) and `fnames_changed` includes a mixture
        # of top-level (i.e. README, etc) files *and* recipes files, it will be too late
        # to easily decide what automation (if any) to run in response to the merge.
        fnames_changed = [files_changed[i]["filename"] for i in range(len(files_changed))]

        if "staged-recipes" in pr["base"]["repo"]["full_name"]:
            # this is staged-recipes, so (probably) create a new feedstock repository

            if pr["title"].lower().startswith("cleanup"):
                return {"status": "skip", "message": "This is an automated cleanup PR. Skipping."}

            # make sure this is a recipe PR (not top-level config or something)
            if not all(fname.startswith("recipes/") for fname in fnames_changed):
                return {"status": "skip", "message": "Not a recipes PR. Skipping."}

            args = (  # type: ignore
                pr["base"]["repo"]["owner"]["login"],
                pr["base"]["ref"],
                pr["number"],
                pr["base"]["repo"]["url"],
            )
            logger.info(f"Calling create_feedstock with args {args}")
            background_tasks.add_task(create_feedstock_repo, *args, **session_kws, gh_kws=gh_kws)
        else:
            # this is not staged recipes, but make sure it's a feedstock, and not some other repo
            if not pr["base"]["repo"]["full_name"].endswith("-feedstock"):
                return {"status": "skip", "message": "This not a -feedstock repo. Skipping."}

            # make sure this is a recipe PR (not config, readme, etc)
            if not all(fname.startswith("feedstock/") for fname in fnames_changed):
                return {"status": "skip", "message": "Not a recipes PR. Skipping."}

            # mypy doesn't like that `args` can have variable length depending on which
            # conditional block it's defined within
            args = (  # type: ignore
                pr["base"]["repo"]["html_url"],
                pr["merge_commit_sha"],
                pr["base"]["repo"]["full_name"],
                pr["base"]["repo"]["url"],
                pr["base"]["ref"],
            )
            background_tasks.add_task(deploy_prod_run, *args, **session_kws, gh_kws=gh_kws)


async def parse_payload(request, payload_bytes, event):
    if event != "dataflow":
        # This is a real github webhook, which can be loaded like this
        return await request.json()
    # This is a webhook sent by our custom GCP Cloud Function. For some reason it can't be
    # parsed with ``await request.json`` so just special-casing for now.
    # TODO: What can we change in this Cloud Function to remove this special-casing? It's
    # defined in https://github.com/pango-forge/dataflow-status-monitoring.
    # Maybe Python ``requests`` payloads are just *inevitably* encoded as query strings, so
    # we would need to use a different method/module/language to get uniformity w/ GitHub?
    qs = parse_qs(payload_bytes.decode("utf-8"))
    return {k: v.pop(0) for k, v in qs.items()}


async def verify_hash_signature(request: Request, payload_bytes: bytes) -> None:
    if hash_signature := request.headers.get("X-Hub-Signature-256", None):
        github_app = get_config().github_app
        webhook_secret = bytes(github_app.webhook_secret, encoding="utf-8")  # type: ignore
        h = hmac.new(webhook_secret, payload_bytes, hashlib.sha256)
        if not hmac.compare_digest(hash_signature, f"sha256={h.hexdigest()}"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Request hash signature invalid."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request does not include a GitHub hash signature header.",
        )


@github_app_router.get(
    "/github/hooks/deliveries",
    summary="Get all webhook deliveries, not filtered by originating feedstock repo.",
    tags=["github_app", "public"],
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
    tags=["github_app", "public"],
)
async def get_delivery(
    id: int,
    response_only: bool = Query(True, description="Return only response body, excluding request."),
    http_session: aiohttp.ClientSession = Depends(http_session),
):
    gh = get_github_session(http_session)
    delivery = await gh.getitem(f"/app/hook/deliveries/{id}", jwt=get_jwt(), accept=ACCEPT)
    return delivery["response"] if response_only else delivery


# Background task helpers -------------------------------------------------------------------------


async def make_dataflow_job_name(recipe_run: SQLModel, gh: GitHubAPI):
    github_app_webhook_url = await get_app_webhook_url(gh)
    # Encode webhook url + recipe run id so that:
    #   1. they are valid gcp labels (max 64 char, no special chars, no uppercase, etc.):
    #      https://cloud.google.com/resource-manager/docs/creating-managing-labels#requirements
    #   2. encoding can be reversed by webhook cloud function to determine:
    #       (a) where (i.e. url) to post job completion webhook
    #       (b) the recipe run id assocated with the job (in the database used by the backend
    #           deployed at this url
    # This feels brittle and has room for improvement but just doing it this way for now
    # to get *something* wired together and working.
    p = urlparse(github_app_webhook_url)
    # if this is a named deployment (review, staging, or prod) we don't need to include the path
    # because it will always be "/github/hooks/" and we don't want to waste valuable space in our
    # 64 char length limit encoding that. but if the path is something else, this is local proxy
    # server, and so we do need to preseve that.
    to_encode = p.netloc if p.path == "/github/hooks/" else p.netloc + p.path
    to_encode += "%"  # control character to separate webhook url encoding from recipe run id
    as_hex = "".join([f"{ord(x):02x}" for x in to_encode])
    # decoding is easier if recipe_run id encoded with an even length, so zero-pad if odd.
    # note we are using ``f"0{recipe_run.id}"``, *not* ``f"{recipe_run_id:02}"`` to pad if odd,
    # because we want the *number of digits* to be even regardless of the length of the odd input.
    recipe_run_id_str = f"0{recipe_run.id}" if len(str(recipe_run.id)) % 2 else str(recipe_run.id)
    encoded_webhook_url_plus_recipe_run_id = as_hex + recipe_run_id_str
    # so, this will be reversable with:
    #   ```
    #   as_pairs = [
    #       a + b for a, b in zip(
    #           encoded_webhook_url_plus_recipe_run_id[::2],
    #           encoded_webhook_url_plus_recipe_run_id[1::2],
    #       )
    #   ]
    #   control_character_idx = [
    #       i for i, val in enumerate(as_pairs) if chr(int(val, 16)) == "%"
    #   ].pop(0)
    #   recipe_run_id = int("".join(as_pairs[control_character_idx + 1:]))
    #   webhook_url = "".join(
    #       [chr(int(val, 16)) for val in as_pairs[:control_character_idx]]
    #   )
    #   ```
    # Finally, dataflow job names *have to* start with a lowercase letter, so prepending "a":
    job_name = f"a{encoded_webhook_url_plus_recipe_run_id}"
    if len(job_name) > 64:
        raise ValueError(f"{len(job_name) = } exceeds max dataflow job name len of 64 chars.")
    return job_name


async def run(
    html_url: str,
    ref: str,
    recipe_run: SQLModel,
    feedstock_spec: str,
    feedstock_subdir: Optional[str] = None,
    *,
    gh: GitHubAPI,
    db_session: Session,
):
    statement = select(MODELS["bakery"].table).where(
        MODELS["bakery"].table.id == recipe_run.bakery_id
    )
    bakery = db_session.exec(statement).one()
    bakery_config = get_config().bakeries[bakery.name]

    subpath = get_storage_subpath_identifier(feedstock_spec, recipe_run)
    # root paths are an interesting configuration edge-case because they combine some stable
    # config (the base path) with some per-recipe config (the subpath). so they are partially
    # initialized when we get them, but we need to complete them here.
    # NOTE: redundant with {job_name} formatting feature in pangeo-forge-runner, but we want to
    # use job_name for identifying the webhook url so we're rolling our own solution for this.
    bakery_config.TargetStorage.root_path = bakery_config.TargetStorage.root_path.format(
        subpath=subpath
    )
    bakery_config.MetadataCacheStorage.root_path = (
        bakery_config.MetadataCacheStorage.root_path.format(subpath=subpath)
    )
    if bakery_config.Bake.bakery_class.endswith("DataflowBakery"):
        bakery_config.Bake.job_name = await make_dataflow_job_name(recipe_run, gh)

    logger.debug(f"Dumping bakery config to json: {bakery_config.dict(exclude_none=True)}")
    # See https://github.com/yuvipanda/pangeo-forge-runner/blob/main/tests/test_bake.py
    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(bakery_config.export_with_secrets(), f)
        f.flush()
        cmd = [
            "pangeo-forge-runner",
            "bake",
            f"--repo={html_url}",
            f"--ref={ref}",
            "--json",
        ]
        if recipe_run.is_test:
            cmd.append("--prune")

        cmd += [f"--Bake.recipe_id={recipe_run.recipe_id}", f"-f={f.name}"]

        if feedstock_subdir:
            cmd.append(f"--feedstock-subdir={feedstock_subdir}")

        logger.debug(f"Running command: {cmd}")

        # We're about to run this recipe, let's update its status to "in_progress"
        recipe_run.status = "in_progress"
        # Start time was first set when recipe run was queued, which could have been ages ago,
        # so if we don't update it now, we won't capture how long the pipeline actually took.
        recipe_run.started_at = datetime.utcnow().replace(microsecond=0)
        db_session.add(recipe_run)
        db_session.commit()
        try:
            out = subprocess.check_output(cmd)
            logger.debug(f"Command output is {out.decode('utf-8')}")
            for line in out.splitlines():
                p = json.loads(line)
                if p.get("status") == "submitted":
                    message = json.loads(recipe_run.message or "{}") | dict(
                        job_name=p["job_name"], job_id=p["job_id"]
                    )
                    recipe_run.message = json.dumps(message)
                    db_session.add(recipe_run)
                    db_session.commit()

        except subprocess.CalledProcessError as e:
            for line in e.output.splitlines():
                p = json.loads(line)
                if p.get("status") == "failed":
                    trace = p["exc_info"]

            logger.error(f"Recipe run {recipe_run} failed with: {trace}")

            recipe_run.status = "completed"
            recipe_run.conclusion = "failure"
            # Add the traceback for this deployment failure to the recipe run, otherwise it could
            # easily get buried in the server logs. TODO: Consider: is there anything of security
            # significance in the call stack captured in the trace?
            message = json.loads(recipe_run.message or "{}")
            recipe_run.message = json.dumps(message | {"trace": trace})
            db_session.add(recipe_run)
            db_session.commit()
            db_session.refresh(recipe_run)
            raise e  # raise the error, so that the calling function knows what happened


# Background tasks --------------------------------------------------------------------------------


async def synchronize(
    head_html_url: str,
    head_sha: str,
    pr_number: str,
    base_api_url: str,
    base_full_name: str,
    *,
    gh: GitHubAPI,
    db_session: Session,
    gh_kws: dict,
):
    logger.info(f"Synchronizing {head_html_url} at {head_sha}.")
    create_request = dict(
        name="synchronize",
        head_sha=head_sha,
        status="in_progress",
        started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        output=dict(
            title="Syncing latest commit to Pangeo Forge Cloud",
            summary="",
        ),
        details_url="https://pangeo-forge.org/",
    )  # required

    checks_response = await gh.post(f"{base_api_url}/check-runs", data=create_request, **gh_kws)
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
        f"--repo={head_html_url}",
        f"--ref={head_sha}",
        "--json",
    ]
    feedstock_subdir = await maybe_specify_feedstock_subdir(base_api_url, pr_number, gh)
    if feedstock_subdir:
        cmd.append(f"--feedstock-subdir={feedstock_subdir}")
    try:
        out = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        for line in e.output.splitlines():
            p = json.loads(line)
            # patch for https://github.com/pangeo-forge/pangeo-forge-orchestrator/issues/132
            if ("status" in p) and p["status"] == "failed":
                tracelines = p["exc_info"].splitlines()
                logger.debug(f"Synchronize errored with:\n {tracelines}")
                update_request = dict(
                    status="completed",
                    conclusion="failure",
                    completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
                    output=dict(
                        title="Synchronize error - click details for summary",
                        summary=tracelines[-1],
                    ),
                )

                await gh.patch(
                    f"{base_api_url}/check-runs/{checks_response['id']}",
                    data=update_request,
                    **gh_kws,
                )
                raise ValueError(tracelines[-1]) from e
        # CalledProcessError's output *should* have a line where "status" == "failed", but just in
        # case it doesn't, raise a NotImplementedError here to prevent moving forward.
        raise NotImplementedError from e

    for line in out.splitlines():
        p = json.loads(line)
        # patch for https://github.com/pangeo-forge/pangeo-forge-orchestrator/issues/132
        if ("status" in p) and p["status"] == "completed":
            meta = p["meta"]
    logger.debug(meta)

    # TODO[IMPORTANT]:
    #   - Add MetaYaml pydantic model to this somewhere. i'd say top level of this repo,
    #     but actually we want it to be user facing somehow). pangeo-forge-runner? its own
    #     repo? or maybe the top-level of this repo, but export a JSON spec on deploy?
    #   - Then at this point in the synchronize task, parse ``meta`` dict into the model?
    #   - As I now think about this, I guess we want to parse ``meta`` dict into pydantic in
    #     pangeo-forge-runner, so that functionality is available to users.

    try:
        feedstock_statement = select(MODELS["feedstock"].table).where(
            MODELS["feedstock"].table.spec == base_full_name
        )
        feedstock = db_session.exec(feedstock_statement).one()
        bakery_statement = select(MODELS["bakery"].table).where(
            MODELS["bakery"].table.name == meta["bakery"]["id"]
        )
        bakery = db_session.exec(bakery_statement).one()
    except (MultipleResultsFound, NoResultFound) as e:
        if isinstance(e, NoResultFound):
            output = dict(
                title="Feedstock and/or bakery not present in database.",
                summary=dedent(
                    f"""\
                    To resolve, a maintainer must ensure both of the following are in database:
                    - **Feedstock**: {base_full_name}
                    - **Bakery**: `{meta["bakery"]["id"]}`
                    """
                ),
            )
        elif isinstance(e, MultipleResultsFound):
            output = dict(
                title="Duplicate feedstock(s) and/or bakeries found in database.",
                summary=dedent(
                    f"""\
                    To resolve, a maintainer must ensure there is only one each of:
                    - **Feedstock**: {base_full_name}
                    - **Bakery**: `{meta["bakery"]["id"]}`
                    in the database.
                    """
                ),
            )
        update_request = dict(
            status="completed",
            conclusion="failure",
            completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
            output=output,
        )

        await gh.patch(
            f"{base_api_url}/check-runs/{checks_response['id']}",
            data=update_request,
            **gh_kws,
        )
        # ok, this seems maybe like the wrong way to do this?
        # just want to raise the same error type but with a custom message
        raise type(e)(json.dumps(output)) from e

    # TODO: Derive `dataset_type` from recipe instance itself; hardcoding for now.
    # See https://github.com/pangeo-forge/pangeo-forge-recipes/issues/268
    # and https://github.com/pangeo-forge/staged-recipes/pull/154#issuecomment-1190925126
    new_models = [
        MODELS["recipe_run"].creation(
            recipe_id=recipe["id"],
            bakery_id=bakery.id,
            feedstock_id=feedstock.id,
            head_sha=head_sha,
            version="",
            started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
            is_test=True,
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
    # TODO: using urllib.parse.parse_qs / urlencode here would be more robust
    query_param = f"feedstock_id={feedstock.id}"
    if backend_netloc != DEFAULT_BACKEND_NETLOC:
        query_param += f"&orchestratorEndpoint={backend_netloc}"
    for model in created:
        summary += f"\n- {FRONTEND_DASHBOARD_URL}/recipe-run/{model.id}?{query_param}"
    update_request = dict(
        status="completed",
        conclusion="success",
        completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        output=dict(title="Recipe runs queued for latest commit", summary=summary),
    )

    await gh.patch(
        f"{base_api_url}/check-runs/{checks_response['id']}", data=update_request, **gh_kws
    )


async def run_recipe_test(
    head_html_url: str,
    base_api_url: str,
    head_sha: str,
    pr_number: str,
    recipe_run: SQLModel,
    feedstock_spec: str,
    reactions_url: str,
    *,
    gh: GitHubAPI,
    db_session: Session,
    gh_kws: dict,
):
    """ """
    await gh.post(reactions_url, data={"content": "rocket"}, **gh_kws)

    # `run_recipe_test` could be called from either staged-recipes *or* a feedstock, therefore,
    # check which one this is, and if it's staged-recipes, specify the subdirectoy name kwarg.
    feedstock_subdir = await maybe_specify_feedstock_subdir(base_api_url, pr_number, gh)
    args = (head_html_url, head_sha, recipe_run, feedstock_spec)
    kws = {"feedstock_subdir": feedstock_subdir} if feedstock_subdir else {}
    logger.info(f"Calling run with args, kws: {args}, {kws}")
    # TODO: create a check run on the head_sha this was deployed from to give
    # a point of user engagement & a details link to recipe run page on pangeo-forge.org
    try:
        await run(*args, **kws, gh=gh, db_session=db_session)
    except subprocess.CalledProcessError:
        await gh.post(reactions_url, data={"content": "confused"}, **gh_kws)
        # We don't need to update the recipe_run in the database or handle the trace here,
        # because that's taken care of inside `run`.


async def triage_test_run_complete(
    recipe_run: SQLModel,
    feedstock_spec: str,
    *,
    gh: GitHubAPI,
    gh_kws: dict,
):
    async for pr in gh.getiter(f"/repos/{feedstock_spec}/pulls", **gh_kws):
        if pr["head"]["sha"] == recipe_run.head_sha:
            comments_url = pr["comments_url"]
            break

    if recipe_run.conclusion == "failure":
        comment = dedent(
            """\
            The test failed, but I'm sure we can find out why!

            Pangeo Forge maintainers are working diligently to provide public logs for contributors.
            That feature is not quite ready yet, however, so please reach out on this thread to a
            maintainer, and they'll help you diagnose the problem.
            """
        )
    elif recipe_run.conclusion == "success":
        if recipe_run.dataset_type == "zarr":
            to_open = dedent(
                f"""\
                import xarray as xr

                store = "{recipe_run.dataset_public_url}"
                ds = xr.open_dataset(store, engine='zarr', chunks={{}})
                ds
                """
            )
        else:
            to_open = dedent(
                f"""\
                Demonstration code for opening {recipe_run.dataset_type = } not implemented yet.
                """
            )
        comment = dedent(
            """\
            :tada: The test run of `{recipe_id}` at {sha} succeeded!

            ```python
            {to_open}
            ```
            """
        ).format(recipe_id=recipe_run.recipe_id, sha=recipe_run.head_sha, to_open=to_open)

    _ = await gh.post(comments_url, data={"body": comment}, **gh_kws)


async def triage_prod_run_complete(
    recipe_run: SQLModel,
    *,
    gh: GitHubAPI,
    gh_kws: dict,
):
    deployment_id = json.loads(recipe_run.message)["deployment_id"]
    environment_url = json.loads(recipe_run.message)["environment_url"]
    await gh.post(
        f"/repos/{recipe_run.feedstock.spec}/deployments/{deployment_id}/statuses",
        # Here's a fun thing we can do because our recipe run model fields are modeled on the
        # GitHub API: pass the recipe_run.conclusion directly through to deployment state.
        data=dict(
            state=recipe_run.conclusion,
            environment_url=environment_url,
        ),
        **gh_kws,
    )
    # Don't need to link deployment to recipe run page here; that was already done when the
    # recipe run was moved to "in_progress" (either by `recipe_run_test` or `deploy_prod_run`).


async def create_feedstock_repo(
    base_repo_owner_login: dict,
    base_ref: str,
    pr_number: str,
    base_repo_api_url: str,
    *,
    gh: GitHubAPI,
    db_session: Session,
    gh_kws: dict,
):
    # (1) check changed files, if we're in a subdir of recipes, then proceed
    src_files = await gh.getitem(f"{base_repo_api_url}/pulls/{pr_number}/files", **gh_kws)
    subdir = src_files[0]["filename"].split("/")[1]
    # (2) make a new repo with name `subdir-feedstock`, plus license + readme
    name = f"{subdir}-feedstock"
    data = dict(
        name=name,
        description=f"Pangeo Forge feedstock for {subdir}.",
        # TODO: link directly to feedstock in database? Problem is we don't know that we're in a
        # production deployment, so will need to conditionally append orchestratorEndpoint param.
        homepage="https://pangeo-forge.org",
        private=False,
        has_issues=True,
        has_projects=False,
        has_wiki=False,
        auto_init=True,
        gitignore_template="Python",
        license_template="apache-2.0",
    )
    logger.debug(f"Creating new feedstock with kws: {data}")
    await gh.post(f"/orgs/{base_repo_owner_login}/repos", data=data, **gh_kws)
    feedstock_spec = f"{base_repo_owner_login}/{name}"
    # (3) TODO: add all contributors to PR as collaborators w/ write permission on repo
    # (4) create a new branch on feedstock repo
    logger.debug(f"Adding 'create-feedstock' branch on feedstock {feedstock_spec}")
    main = await gh.getitem(f"/repos/{feedstock_spec}/branches/main", **gh_kws)
    working_branch = await gh.post(
        f"/repos/{feedstock_spec}/git/refs",
        data=dict(
            ref="refs/heads/create-feedstock",
            sha=main["commit"]["sha"],
        ),
        **gh_kws,
    )
    # (5) add contents to new branch
    for f in src_files:
        src = f["filename"]
        dst = f"feedstock/{os.path.basename(src)}"
        logger.debug(f"Copying file {src} -> {dst}")

        content = await gh.getitem(f["contents_url"], **gh_kws)
        await gh.put(
            f"/repos/{feedstock_spec}/contents/{dst}",
            data=dict(
                message=f"Adding {dst}",
                content=content["content"],
                branch="create-feedstock",
            ),
            **gh_kws,
        )
    # (6) open PR
    open_pr = await gh.post(
        f"/repos/{feedstock_spec}/pulls",
        data=dict(
            title=f"Create {feedstock_spec}",
            head="create-feedstock",
            base="main",
        ),
        **gh_kws,
    )
    # (7) add new feedstock to database
    new_fstock_model = MODELS["feedstock"].creation(spec=feedstock_spec)
    db_model = MODELS["feedstock"].table.from_orm(new_fstock_model)
    db_session.add(db_model)
    db_session.commit()
    # (8) merge PR - this deploys prod run via another call to /github/hooks route
    merged = await gh.put(f"/repos/{feedstock_spec}/pulls/{open_pr['number']}/merge", **gh_kws)
    # (9) delete PR branch
    assert merged["merged"]
    await gh.delete(working_branch["url"], **gh_kws)
    # (9) delete files from staged-recipes
    base_branch = await gh.getitem(f"{base_repo_api_url}/branches/{base_ref}", **gh_kws)
    cleanup_branch = await gh.post(
        f"{base_repo_api_url}/git/refs",
        data=dict(
            ref=f"refs/heads/cleanup-{int(datetime.now().timestamp())}",
            sha=base_branch["commit"]["sha"],
        ),
        **gh_kws,
    )
    for f in src_files:
        await gh.delete(
            f"{base_repo_api_url}/contents/{f['filename']}",
            data=dict(
                message=f"Delete {f['filename']}",
                sha=f["sha"],
                branch=cleanup_branch["ref"],
            ),
            **gh_kws,
        )
    cleanup_pr = await gh.post(
        f"{base_repo_api_url}/pulls",
        data=dict(
            title=f"Cleanup {feedstock_spec}",
            head=cleanup_branch["ref"],
            base=base_ref,
        ),
        **gh_kws,
    )
    merged = await gh.put(f"{base_repo_api_url}/pulls/{cleanup_pr['number']}/merge", **gh_kws)
    assert merged["merged"]
    await gh.delete(cleanup_branch["url"], **gh_kws)


async def deploy_prod_run(
    base_html_url: str,
    merge_commit_sha: str,
    base_full_name: str,
    base_api_url: str,
    base_ref: str,
    *,
    gh: GitHubAPI,
    db_session: Session,
    gh_kws: dict,
):
    # (1) expand meta
    cmd = [
        "pangeo-forge-runner",
        "expand-meta",
        f"--repo={base_html_url}",
        f"--ref={merge_commit_sha}",
        "--json",
    ]
    logger.info(f"Calling subprocess {cmd}")
    try:
        out = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        # TODO: report this error to users somehow
        raise e

    for line in out.splitlines():
        p = json.loads(line)
        # patch for https://github.com/pangeo-forge/pangeo-forge-orchestrator/issues/132
        if ("status" in p) and p["status"] == "completed":
            meta = p["meta"]
    logger.debug(f"Retrieved meta: {meta}")

    # (2) find the feedstock and bakery in the database
    try:
        feedstock_statement = select(MODELS["feedstock"].table).where(
            MODELS["feedstock"].table.spec == base_full_name
        )
        feedstock = db_session.exec(feedstock_statement).one()
        bakery_statement = select(MODELS["bakery"].table).where(
            MODELS["bakery"].table.name == meta["bakery"]["id"]
        )
        bakery = db_session.exec(bakery_statement).one()
    except NoResultFound as e:
        # TODO: notify the user of this somehow
        raise e
    logger.debug(f"Found feedstock: {feedstock}")
    logger.debug(f"Found bakery: {bakery}")

    # (3) create recipe runs for every recipe in meta
    created = []
    for recipe in meta["recipes"]:
        gh_deployment = await gh.post(
            f"{base_api_url}/deployments",
            data=dict(
                ref=base_ref,
                environment=recipe["id"],
            ),
            **gh_kws,
        )
        logger.debug(f"Created github deployment: {gh_deployment}")
        model = MODELS["recipe_run"].creation(
            recipe_id=recipe["id"],
            bakery_id=bakery.id,
            feedstock_id=feedstock.id,
            head_sha=merge_commit_sha,
            version="",
            started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
            is_test=False,
            dataset_type="zarr",
            message=json.dumps({"deployment_id": gh_deployment["id"]}),
        )

        db_model = MODELS["recipe_run"].table.from_orm(model)
        db_session.add(db_model)
        db_session.commit()
        db_session.refresh(db_model)
        logger.debug(f"Created recipe run: {gh_deployment}")
        created.append(db_model)

    # (4) deploy every recipe run; `recipe_run.is_test=False` ensures `run` won't prune.
    for recipe_run in created:
        args = (base_html_url, merge_commit_sha, recipe_run, feedstock.spec)
        logger.info(f"Calling run with args: {args}")
        try:
            await run(*args, gh=gh, db_session=db_session)  # type: ignore
        except subprocess.CalledProcessError:
            deployment_id = json.loads(recipe_run.message)["deployment_id"]
            await gh.post(
                f"{base_api_url}/deployments/{deployment_id}/statuses",
                data=dict(status="failure"),
                **gh_kws,
            )
        # Don't update recipe_run as "failed" here, that's handled inside `run`.
        # Don't update recipe_run as "in_progress" here, that's handled inside `run`.
        # (4.5) Update deployment with link to recipe run page
        logger.debug("HEREEEEEEEEEEEEEEEEEe")
        logger.debug(recipe_run.message)
        deployment_id = json.loads(recipe_run.message)["deployment_id"]
        environment_url = (
            "https://pangeo-forge.org/dashboard/"
            f"recipe-run/{recipe_run.id}?feedstock_id={feedstock.id}"
        )
        # TODO: using urllib.parse.parse_qs / urlencode here would be more robust
        # NOTE: redundant with one other block above. could combine into one function.
        backend_app_webhook_url = await get_app_webhook_url(gh)
        backend_netloc = urlparse(backend_app_webhook_url).netloc
        if backend_netloc != DEFAULT_BACKEND_NETLOC:
            environment_url += f"&orchestratorEndpoint={backend_netloc}"
        await gh.post(
            f"{base_api_url}/deployments/{deployment_id}/statuses",
            data=dict(
                state="in_progress",
                environment_url=environment_url,
            ),
            **gh_kws,
        )
        message = json.loads(recipe_run.message)
        # save environment url for reuse when job completes, in `triage_prod_run_complete`
        recipe_run.message = json.dumps(message | {"environment_url": environment_url})
        db_session.add(recipe_run)
        db_session.commit()
        db_session.refresh(recipe_run)
