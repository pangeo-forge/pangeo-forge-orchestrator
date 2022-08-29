import hashlib
import hmac
import json
import subprocess
import tempfile
import time
from datetime import datetime
from textwrap import dedent
from typing import List, Tuple
from urllib.parse import parse_qs, urlparse

import aiohttp
import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
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


def get_github_session(http_session: aiohttp.ClientSession):
    return GitHubAPI(http_session, "pangeo-forge")


def html_to_api_url(html_url: str) -> str:
    return html_url.replace("github.com", "api.github.com/repos")


def html_url_to_repo_full_name(html_url: str) -> str:
    return html_url.replace("https://github.com/", "")


def get_jwt():
    """Adapted from https://github.com/Mariatta/gh_app_demo"""

    github_app = get_config().github_app
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": github_app.id,
    }
    bearer_token = jwt.encode(payload, github_app.private_key, algorithm="RS256")

    return bearer_token


async def get_access_token(gh: GitHubAPI):
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


async def maybe_specify_feedstock_subdir(
    cmd: List[str],
    api_url: str,
    pr_number: str,
    gh: GitHubAPI,
) -> List[str]:
    """If this is staged-recipes, add the --feedstock-subdir option to the command."""

    if "staged-recipes" in api_url:
        token = await get_access_token(gh)
        files = await gh.getitem(
            f"{api_url}/pulls/{pr_number}/files",
            oauth_token=token,
            accept=ACCEPT,
        )
        # TODO: make subdir parsing more robust. currently, the next line will parse
        #   ``[{'filename': 'recipes/new-dataset/recipe.py'}]`` --> 'new-dataset'
        # but does not account for any edge cases or error conditions.
        subdir = files[0]["filename"].split("/")[1]
        cmd.append(f"--feedstock-subdir=recipes/{subdir}")

    return cmd


def get_storage_subpath_identifier(recipe_run: SQLModel):
    # TODO: make this identifier better, and **differentiate test vs. prod runs**.
    return f"{recipe_run.recipe_id}-{int(datetime.now().timestamp())}"


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
    github_app = get_config().github_app
    webhook_secret = bytes(github_app.webhook_secret, encoding="utf-8")  # type: ignore
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
    token = await get_access_token(gh)
    gh_kws = dict(oauth_token=token, accept=ACCEPT)

    event = request.headers.get("X-GitHub-Event")
    if event != "dataflow":
        # This is a real github webhook, which can be loaded like this
        payload = await request.json()
    else:
        # This is a webhook sent by our custom GCP Cloud Function. For some reason it can't be
        # parsed with ``await request.json`` so just special-casing for now.
        # TODO: What can we change in this Cloud Function to remove this special-casing? It's
        # defined in https://github.com/pango-forge/dataflow-status-monitoring.
        # Maybe Python ``requests`` payloads are just *inevitably* encoded as query strings, so
        # we would need to use a different method/module/language to get uniformity w/ GitHub?
        qs = parse_qs(payload_bytes.decode("utf-8"))
        payload = {k: v.pop(0) for k, v in qs.items()}

    if event == "pull_request" and payload["action"] in ("synchronize", "opened"):
        pr = payload["pull_request"]

        maybe_pass = await pass_if_deployment_not_selected(pr["labels"], gh=gh)
        if maybe_pass["status"] == "pass":
            return maybe_pass

        args = (pr["base"]["repo"]["html_url"], pr["head"]["sha"], pr["number"])
        background_tasks.add_task(synchronize, *args, **session_kws)
        return {"status": "ok", "background_tasks": [{"task": "synchronize", "args": args}]}

    elif event == "issue_comment" and payload["action"] == "created":
        comment = payload["comment"]
        comment_body = comment["body"]
        reactions_url = comment["reactions"]["url"]

        pr = await gh.getitem(payload["issue"]["pull_request"]["url"], **gh_kws)

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
                payload["repository"]["html_url"],
                pr["head"]["sha"],
                pr["number"],
                matching_recipe_run,
                reactions_url,
            )
            background_tasks.add_task(run_recipe_test, *args, **session_kws, gh_kws=gh_kws)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No handling implemented for this event type.",
            )

    elif event == "dataflow" and payload["action"] == "completed":
        logger.info(f"Received dataflow webhook with {payload = }")
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
        if recipe_run.conclusion == "success":
            bakery_config = get_config().bakeries[bakery.name]
            subpath = get_storage_subpath_identifier(recipe_run)
            root_path = bakery_config.TargetStorage.root_path.format(subpath=subpath)
            recipe_run.dataset_public_url = bakery_config.TargetStorage.public_url.format(  # type: ignore
                root_path=root_path
            )
        db_session.add(recipe_run)
        db_session.commit()

        # Wow not every day you google a error and see a comment on it by Guido van Rossum
        # https://github.com/python/mypy/issues/1174#issuecomment-175854832
        args: Tuple[SQLModel, SQLModel] = (recipe_run, feedstock)  # type: ignore
        if recipe_run.is_test:
            background_tasks.add_task(triage_test_run_complete, *args, gh=gh, gh_kws=gh_kws)
        else:
            background_tasks.add_task(triage_prod_run_complete, *args, gh=gh, gh_kws=gh_kws)

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


async def synchronize(
    html_url: str,
    head_sha: str,
    pr_number: str,
    *,
    gh: GitHubAPI,
    db_session: Session,
):
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
        f"--repo={html_url}",
        f"--ref={head_sha}",
        "--json",
    ]
    cmd = await maybe_specify_feedstock_subdir(cmd, api_url, pr_number, gh)
    try:
        out = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        for line in e.output.splitlines():
            p = json.loads(line)
            if p["status"] == "failed":
                tracelines = p["exc_info"].splitlines()
                if tracelines[-1].startswith("FileNotFoundError"):
                    # A required file is missing: either meta.yaml or recipe.py
                    update_request = dict(
                        status="completed",
                        conclusion="failure",
                        completed_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
                        output=dict(title="FileNotFoundError", summary=tracelines[-1]),
                    )
                    _ = await update_check_run(gh, api_url, checks_response["id"], update_request)
                    raise ValueError(tracelines[-1]) from e
                else:
                    raise NotImplementedError from e
        # CalledProcessError's output *should* have a line where "status" == "failed", but just in
        # case it doesn't, raise a NotImplementedError here to prevent moving forward.
        raise NotImplementedError from e

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
    html_url: str,
    head_sha: str,
    pr_number: str,
    recipe_run: SQLModel,
    reactions_url: str,
    *,
    gh: GitHubAPI,
    db_session: Session,
    gh_kws: dict,
):
    """ """
    api_url = html_to_api_url(html_url)
    github_app_webhook_url = await get_app_webhook_url(gh)

    statement = select(MODELS["bakery"].table).where(
        MODELS["bakery"].table.id == recipe_run.bakery_id
    )
    matching_bakery = db_session.exec(statement).one()
    bakery_config = get_config().bakeries[matching_bakery.name]

    subpath = get_storage_subpath_identifier(recipe_run)
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
    as_hex = "".join(["{:02x}".format(ord(x)) for x in to_encode])
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
    bakery_config.Bake.job_name = f"a{encoded_webhook_url_plus_recipe_run_id}"

    logger.debug(f"Dumping bakery config to json: {bakery_config.dict()}")
    # See https://github.com/yuvipanda/pangeo-forge-runner/blob/main/tests/test_bake.py
    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
        json.dump(bakery_config.dict(), f)
        f.flush()
        cmd = [
            "pangeo-forge-runner",
            "bake",
            f"--repo={html_url}",
            f"--ref={head_sha}",
            "--json",
            "--prune",
            f"--Bake.recipe_id={recipe_run.recipe_id}",  # NOTE: under development
            f"-f={f.name}",
        ]
        cmd = await maybe_specify_feedstock_subdir(cmd, api_url, pr_number, gh)
        logger.debug(f"Running command: {cmd}")

        # We're about to run this recipe, let's update its status to "in_progress"
        recipe_run.status = "in_progress"
        # TODO: update recipe_run.started_at time? It was initially set on creation.
        db_session.add(recipe_run)
        db_session.commit()
        _ = await gh.post(reactions_url, data={"content": "rocket"}, **gh_kws)
        try:
            out = subprocess.check_output(cmd)
            logger.debug(f"Command output is {out.decode('utf-8')}")
        except subprocess.CalledProcessError as e:
            # Something went wrong, let's update the recipe_run status to "failed"
            # TODO: Confirm this works. I don't think we need to get the model back from the database.
            recipe_run.status = "completed"
            recipe_run.conclusion = "failure"
            db_session.add(recipe_run)
            db_session.commit()
            _ = await gh.post(reactions_url, data={"content": "confused"}, **gh_kws)
            raise ValueError(e.output) from e


async def triage_test_run_complete(
    recipe_run: SQLModel,
    feedstock: SQLModel,
    *,
    gh: GitHubAPI,
    gh_kws: dict,
):
    async for pr in gh.getiter(f"/repos/{feedstock.spec}/pulls", **gh_kws):
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


async def triage_prod_run_complete():
    pass
