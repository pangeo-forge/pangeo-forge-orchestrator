import os
import random
from pathlib import Path

import pytest
import pytest_asyncio
import yaml  # type: ignore
from gidgethub.aiohttp import GitHubAPI

from pangeo_forge_orchestrator.http import HttpSession
from pangeo_forge_orchestrator.routers.github_app import get_access_token


@pytest_asyncio.fixture(scope="session")
async def gh() -> GitHubAPI:
    """A global gidgethub session to use throughout the integration tests."""

    http_session = HttpSession()
    yield GitHubAPI(http_session)
    await http_session.stop()


@pytest_asyncio.fixture
async def gh_kws(gh: GitHubAPI) -> dict:
    # this entire test relies on the assumption that it is being called from the root of the
    # pangeo-forge-orchestrator repo, and therefore has access to the `dev-app-proxy` github app
    # creds. if these creds are not decrypted before this test is run, strange non-self-describing
    # errors may occur, so before we run the test, let's just make sure the creds are decrypted.
    # NOTE: the path to these credentials will need to change after traitlets refactor goes in.
    with open(Path(__file__).parent.parent / "secrets/config.dev-app-proxy.yaml") as f:
        if "sops" in yaml.safe_load(f):
            raise ValueError(
                "GitHub App `dev-app-proxy` credentials are encrypted. "
                "Decrypt these credentials before running this test."
            )
    # okay, the credentials are decrypted, so let's move along with the test.
    token = await get_access_token(gh)
    return dict(oauth_token=token, accept="application/vnd.github+json")


@pytest.fixture
def app_url() -> str:
    """Url on the public internet at which the app to test against is currently running."""
    return os.environ["REVIEW_APP_URL"]


@pytest.fixture
def gh_workflow_run_id() -> str:
    """Identified the GitHub Workflow run which called this test."""
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
async def pr_label(gh: GitHubAPI, gh_kws: dict, base: str, app_url: str):
    label_name_fmt = "fwd:{app_url}"
    if "smee" not in app_url:
        # smee proxy urls do not take the route path; heroku review apps do.
        label_name_fmt += "/github/hooks/"

    exists = False
    async for label in gh.getiter(f"repos/{base}/labels", **gh_kws):
        if label["name"] == label_name_fmt.format(app_url=app_url):
            exists = True
            break
    if not exists:
        label = gh.post(
            f"/repos/{base}/labels",
            data=dict(
                name=f"fwd:{app_url}/github/hooks/",
                color=f"{random.randint(0, 0xFFFFFF):06x}",
                description="Tells dev-app-proxy GitHub App to forward webhooks to specified url.",
            ),
            **gh_kws,
        )
    yield label["name"]
    # TODO: delete label after every test? it could certainly be reused multiple times if not.
    # if we do delete the label here, then the check to see if it exists would only hit if the label
    # had been manually created outside a test session, or if the test runner happened to to have
    # errored out on the prior test attempt (before the label had been deleted).


@pytest_asyncio.fixture(scope="session")
async def staged_recipes_pr(
    gh: GitHubAPI,
    gh_kws: dict,
    gh_workflow_run_id: str,
    source_pr: dict[str, str],
    base: str,
    pr_label: str,
):
    """Makes a PR to ``pforgetest/test-staged-recipes`` and labels it ``f"fwd:{app_url}{route}"``,
    where ``{route}`` is optionally the path at which the app running at ``app_url`` receives
    GitHub Webhooks. The label ``f"fwd:{app_url}{route}"`` informs the ``dev-app-proxy`` GitHub App
    where to forward webhooks originating from the PR. After the PR is created, its identifying
    information is yielded to the test function using this fixture. When control is returned to this
    fixture, the PR and its associated branch are closed & cleaned-up.
    """
    # create a new branch on the test repo with a descriptive name.
    # (in the typical contribution process, contributions may likely be from forks. the deviation
    # from that process here may introduce some sublte differences with production. for now, we are
    # accepting that as the cost for doing this more simply; i.e., all within a single repo.)
    main = await gh.getitem(f"/repos/{base}/branches/main", **gh_kws)
    working_branch = await gh.post(  # noqa: F841
        f"/repos/{base}/git/refs",
        data=dict(
            ref=f"refs/heads/{gh_workflow_run_id}",
            sha=main["commit"]["sha"],
        ),
        **gh_kws,
    )

    # populate that branch with content files from the source pr
    src_files = await gh.getitem(
        f"{source_pr['repo_full_name']}/pulls/{source_pr['pr_number']}/files",
        **gh_kws,
    )
    for f in src_files:
        content = await gh.getitem(f["contents_url"], **gh_kws)
        await gh.put(
            f"/repos/{base}/contents/{f['filename']}",
            data=dict(
                message=f"Adding {f['filename']}",
                content=content["content"],
                branch=gh_workflow_run_id,
            ),
            **gh_kws,
        )

    # open a pr against pforgetest/test-staged-recipes:main
    pr = await gh.post(
        f"/repos/{base}/pulls",
        data=dict(
            title=f"[CI] Automated PR for workflow run {gh_workflow_run_id}",
            head=gh_workflow_run_id,
            body=(
                ":robot: Created by https://github.com/pangeo-forge/pangeo-forge-orchestrator"
                f"/actions/runs/{gh_workflow_run_id}",
            ),
            base="main",
        ),
        **gh_kws,
    )

    # label the pr so the dev-app-proxy knows where to forward webhooks originating from this pr
    gh.put(f"/repos/{base}/issues/{pr['number']}/labels", data=dict(labels=[pr_label]), **gh_kws)

    yield pr

    # close pr and cleanup branch
    ...


def test_dataflow(staged_recipes_pr):
    ...
    #
