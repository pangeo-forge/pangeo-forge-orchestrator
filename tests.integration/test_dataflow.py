import os
import random
import time
from urllib.parse import urlparse

import aiohttp
import jwt
import pytest
import pytest_asyncio
from gidgethub.aiohttp import GitHubAPI
from gidgethub.apps import get_installation_access_token
from pydantic import BaseModel, SecretStr


class GitHubApp(BaseModel):
    name: str
    id: int
    private_key: SecretStr


@pytest.fixture(scope="session")
def github_app() -> GitHubApp:
    return GitHubApp(
        name="dev-app-proxy",
        id=238613,
        private_key=os.environ["DEV_APP_PROXY_GITHUB_APP_PRIVATE_KEY"],
    )


@pytest_asyncio.fixture
async def gh(github_app: GitHubApp) -> GitHubAPI:
    """A global gidgethub session to use throughout the integration tests."""

    async with aiohttp.ClientSession() as session:
        yield GitHubAPI(session, github_app.name)


@pytest_asyncio.fixture
async def gh_token(github_app: GitHubApp, gh: GitHubAPI, gh_kws: dict) -> SecretStr:

    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": github_app.id,
    }
    gh_jwt = jwt.encode(payload, github_app.private_key.get_secret_value(), algorithm="RS256")

    async for installation in gh.getiter("/app/installations", jwt=gh_jwt, **gh_kws):
        # dev-app-proxy is only installed in one org (i.e., pforgetest), so
        # the first iteration will give us the installation_id we're after
        installation_id = installation["id"]
        break
    token_response = await get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=github_app.id,
        private_key=github_app.private_key.get_secret_value(),
    )
    # wrap in SecretStr to avoid leaking in failed test logs,
    # see https://github.com/pytest-dev/pytest/issues/8613
    return SecretStr(token_response["token"])


@pytest.fixture
def gh_kws() -> dict:
    return {"accept": "application/vnd.github+json"}


@pytest.fixture
def app_netloc() -> str:
    """Url on the public internet at which the app to test against is currently running."""
    return urlparse(os.environ["REVIEW_APP_URL"]).netloc


@pytest.fixture
def gh_workflow_run_id() -> str:
    """Identifies the GitHub Workflow run which called this test."""
    return os.environ["GH_WORKFLOW_RUN_ID"]


@pytest.fixture
def source_pr() -> dict[str, str]:
    """A PR to replicate for this test."""
    return dict(
        repo_full_name=os.environ["SOURCE_REPO_FULL_NAME"],
        pr_number=os.environ["SOURCE_REPO_PR_NUMBER"],
    )


@pytest.fixture
def base(source_pr):
    if "staged-recipes" in source_pr["repo_full_name"]:
        return "pforgetest/test-staged-recipes"
    elif source_pr["repo_full_name"].endswith("-feedstock"):
        # TODO: add a repo in `pforgetest` which can accept prs from any feedstock.
        # this would essentially be just a blank repo containing an empty `feedstock/` directory.
        raise NotImplementedError


@pytest_asyncio.fixture
async def pr_label(gh: GitHubAPI, gh_token: SecretStr, gh_kws: dict, base: str, app_netloc: str):
    label_name_fmt = "fwd:{app_netloc}"
    if "smee" not in app_netloc:
        # smee proxy urls do not take the route path; heroku review apps do.
        label_name_fmt += "/github/hooks/"

    exists = False
    async for label in gh.getiter(f"repos/{base}/labels", **gh_kws):
        if label["name"] == label_name_fmt.format(app_netloc=app_netloc):
            exists = True
            break
    if not exists:
        label = await gh.post(
            f"/repos/{base}/labels",
            data=dict(
                name=f"fwd:{app_netloc}/github/hooks/",
                color=f"{random.randint(0, 0xFFFFFF):06x}",
                description="Tells dev-app-proxy GitHub App to forward webhooks to specified url.",
            ),
            oauth_token=gh_token.get_secret_value(),
            **gh_kws,
        )
    yield label["name"]
    # TODO: delete label after every test? it could certainly be reused multiple times if not.
    # if we do delete the label here, then the check to see if it exists would only hit if the label
    # had been manually created outside a test session, or if the test runner happened to to have
    # errored out on the prior test attempt (before the label had been deleted).


@pytest_asyncio.fixture
async def staged_recipes_pr(
    gh: GitHubAPI,
    gh_token: SecretStr,
    gh_kws: dict,
    gh_workflow_run_id: str,
    source_pr: dict[str, str],
    base: str,
    pr_label: str,
):
    """Makes a PR to ``pforgetest/test-staged-recipes`` with labels ``f"fwd:{app_netloc}{route}"``,
    where ``{route}`` is optionally the path at which the app running at ``app_netloc`` receives
    GitHub Webhooks. The label ``f"fwd:{app_netloc}{route}"`` informs the ``dev-app-proxy`` GitHub
    App where to forward webhooks originating from the PR. After the PR is created, its identifying
    information is yielded to the test function using this fixture. When control is returned to this
    fixture, the PR and its associated branch are closed & cleaned-up.
    """
    # create a new branch on the test repo with a descriptive name.
    # (in the typical contribution process, contributions may likely be from forks. the deviation
    # from that process here may introduce some sublte differences with production. for now, we are
    # accepting that as the cost for doing this more simply; i.e., all within a single repo.)
    main = await gh.getitem(f"/repos/{base}/branches/main", **gh_kws)
    working_branch = await gh.post(
        f"/repos/{base}/git/refs",
        data=dict(
            ref=f"refs/heads/actions/runs/{gh_workflow_run_id}",
            sha=main["commit"]["sha"],
        ),
        oauth_token=gh_token.get_secret_value(),
        **gh_kws,
    )

    # populate that branch with content files from the source pr
    src_files = await gh.getitem(
        f"repos/{source_pr['repo_full_name']}/pulls/{source_pr['pr_number']}/files",
        **gh_kws,
    )

    async def add_file(f):
        content = await gh.getitem(f["contents_url"], **gh_kws)
        await gh.put(
            f"/repos/{base}/contents/{f['filename']}",
            data=dict(
                message=f"Adding {f['filename']}",
                content=content["content"],
                branch=f"actions/runs/{gh_workflow_run_id}",
            ),
            oauth_token=gh_token.get_secret_value(),
            **gh_kws,
        )

    # add first source file to working branch. see commend above where `add_file` is
    # called a second time, below, for why both files are not added at the same time.
    await add_file(src_files[0])

    # open a pr against pforgetest/test-staged-recipes:main
    pr = await gh.post(
        f"/repos/{base}/pulls",
        data=dict(
            title=f"[CI] Automated PR for workflow run {gh_workflow_run_id}",
            head=f"actions/runs/{gh_workflow_run_id}",
            body=(
                ":robot: Created for test run https://github.com/pangeo-forge/"
                f"pangeo-forge-orchestrator/actions/runs/{gh_workflow_run_id}\n"
                f":memo: Which is testing {pr_label.replace('fwd:', 'https://')}"
            ),
            base="main",
        ),
        oauth_token=gh_token.get_secret_value(),
        **gh_kws,
    )

    # label the pr so the dev-app-proxy knows where to forward webhooks originating from this pr
    await gh.put(
        f"/repos/{base}/issues/{pr['number']}/labels",
        data=dict(labels=[pr_label]),
        oauth_token=gh_token.get_secret_value(),
        **gh_kws,
    )

    # add the second source file (after labeling, so that the `synchronize` task will be forwarded)
    # for explanation of why files are added one at a time (rather than at the same time) see:
    # https://github.com/pangeo-forge/pangeo-forge-orchestrator/pull/226#issuecomment-1423337307
    await add_file(src_files[1])

    yield pr

    # close pr and delete branch
    await gh.patch(
        pr["url"],
        data=dict(state="closed"),
        oauth_token=gh_token.get_secret_value(),
        **gh_kws,
    )
    await gh.delete(
        working_branch["url"],
        oauth_token=gh_token.get_secret_value(),
        **gh_kws,
    )


@pytest.mark.asyncio
async def test_dataflow(
    gh: GitHubAPI,
    gh_token: SecretStr,
    gh_kws: dict,
    base: str,
    staged_recipes_pr: dict,
):
    time.sleep(10)

    await gh.post(
        f"/repos/{base}/issues/{staged_recipes_pr['number']}/comments",
        data=dict(body="/run gpcp-from-gcs"),
        oauth_token=gh_token.get_secret_value(),
        **gh_kws,
    )

    time.sleep(60)
