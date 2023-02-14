import asyncio
import json
import os
import random
import subprocess
import time
from urllib.parse import urljoin, urlparse

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
        # the private key is passed to the env as a `\n`-delimited, single line string from github
        # repository secrets. when passed to the env, single backslash `\n`s become double `\\n`s,
        # so that needs to be reversed here. this is just one of many possible ways to manage
        # multiline private keys in the env. and for our case, i believe the simplest option;
        # see also: https://github.com/dwyl/learn-environment-variables/issues/17.
        private_key=os.environ["DEV_APP_PROXY_GITHUB_APP_PRIVATE_KEY"].replace("\\n", "\n"),
        # NOTE: ☝️ this ☝️ credential **must match** the latest version stored in the SOPS-encrypted
        # private key for the `dev-app-proxy` app stored in pangeo-forge-orchestrator. When that key
        # rotated, this corresponding credential in github repository secrets must also be updated.
        # we are duplicating this credential in two places because, for ci testing, it's much simpler
        # to source this from github repository secrets than it would be to SOPS-decrypt from disk.
        # the cost of that simplicity, is this duplication.
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
def app_url() -> str:
    """The review app url as provided by Heroku."""
    return os.environ["REVIEW_APP_URL"]


@pytest.fixture
def app_netloc(app_url) -> str:
    """Netloc of review app as parsed from app_url fixture."""
    return urlparse(app_url).netloc


@pytest.fixture
def app_recipe_runs_route(app_url) -> str:
    """Route on review app under test at which recipe runs can be retrieved."""
    return urljoin(app_url, "/recipe_runs/")


@pytest.fixture
def gh_workflow_run_id() -> str:
    """Identifies the GitHub Workflow run which called this test."""
    return os.environ["GH_WORKFLOW_RUN_ID"]


@pytest.fixture
def base():
    """The base repo against which the reference (i.e. source) PR has been made."""
    return "pforgetest/test-staged-recipes"


@pytest.fixture
def pr_number_and_recipe_id() -> tuple[str, str]:
    pr_number, recipe_id = os.environ["PR_NUMBER_AND_RECIPE_ID"].split("::")
    return pr_number, recipe_id


@pytest.fixture
def source_pr_number(pr_number_and_recipe_id) -> dict[str, str]:
    """The number of a PR on pforgetest/test-staged-recipes to replicate for this test."""
    pr_number, _ = pr_number_and_recipe_id
    return pr_number


@pytest.fixture
def recipe_id(pr_number_and_recipe_id) -> str:
    """The recipe_id of the recipe defined in the PR to run during this test."""
    _, recipe_id = pr_number_and_recipe_id
    return recipe_id


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
async def recipe_pr(
    gh: GitHubAPI,
    gh_token: SecretStr,
    gh_kws: dict,
    gh_workflow_run_id: str,
    source_pr_number: str,
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
        f"repos/{base}/pulls/{source_pr_number}/files",
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

    # wait a moment to make sure new file is set on github, then get the pr
    # in its current state (otherwise head_sha will not reflect latests commit)
    await asyncio.sleep(3)
    completed_pr = await gh.getitem(f"/repos/{base}/pulls/{pr['number']}", **gh_kws)

    print(f"\nYielding {completed_pr['head']['sha'] = } from recipes_pr fixture...")
    yield completed_pr

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


@pytest_asyncio.fixture
async def recipe_run_id(recipe_pr: dict, app_recipe_runs_route: str):
    # at the start of this test, the recipes_pr fixture has already made a pr on github, but we
    # don't know exactly how long it take for that pr to be synchronized to the review app, so we
    # run a loop to check for when the synchronization is complete.

    # (when heroku re-builds a review app that has previously been built, the database attached to
    # that review app persists between builds. the database is only reset if the review app is
    # deleted, not simply rebuilt. therefore, even though each invocation of this test creates
    # just one recipe_run, there can easily be many recipe runs in the heroku review app database.
    # as such, we parse which specific recipe_run we're currently testing by comparing head_shas.)
    await asyncio.sleep(10)
    start = time.time()
    print("Querying review app database for recipe run id...")
    while True:
        elapsed = time.time() - start
        async with aiohttp.ClientSession() as session:
            get_runs = await session.get(app_recipe_runs_route)
            runs = await get_runs.json()
        if any([r["head_sha"] == recipe_pr["head"]["sha"] for r in runs]):
            run_id = [r for r in runs if r["head_sha"] == recipe_pr["head"]["sha"]][0]["id"]
            print(f"Found matching recipe run in review app database with recipe_{run_id = }...")
            break
        elif elapsed > 30:
            # synchronization should only take a few seconds, so if more than 30
            # seconds has elapsed, something has gone wrong and we should bail out.
            pytest.fail(f"Time {elapsed = } on synchronization.")
        else:
            # if no head_shas match, the sync task may
            # still be running, so wait 2s then retry.
            await asyncio.sleep(5)
    yield run_id


@pytest_asyncio.fixture
async def dataflow_job_id(
    recipe_run_id: int,
    app_recipe_runs_route: str,
    gh: GitHubAPI,
    gh_token: SecretStr,
    gh_kws: dict,
    base: str,
    recipe_pr: dict,
    recipe_id: str,
):
    # now we know the pr is synced, it's time to dispatch the `/run` command
    comment_body = f"/run {recipe_id}"
    print(f"Making comment on test PR with {comment_body = }")
    await gh.post(
        f"/repos/{base}/issues/{recipe_pr['number']}/comments",
        data=dict(body=comment_body),
        oauth_token=gh_token.get_secret_value(),
        **gh_kws,
    )
    # start polling the review app database to see if the job has been deployed to dataflow.
    # if the job was deployed to dataflow, a job_id field will exist in the recipe_run message.
    print("Polling review app for dataflow job submission status...")
    start = time.time()
    while True:
        elapsed = time.time() - start
        async with aiohttp.ClientSession() as session:
            get_run = await session.get(urljoin(app_recipe_runs_route, str(recipe_run_id)))
            run = await get_run.json()
        message = json.loads(run["message"] or "{}")
        if "job_id" in message:
            job_id = message["job_id"]
            print(f"Confirmed dataflow job submitted with {job_id = }")
            break
        elif elapsed > 60 * 5:
            # job submission is taking longer than 5 minutes, something must be wrong, so bail.
            pytest.fail(f"Time {elapsed = } on job submission.")
        else:
            # if there is no job_id in the message, and less than 5 minutes has elapsed in this
            # loop, the job submission might still be in process, so wait 30 seconds and retry
            await asyncio.sleep(30)
    yield job_id


@pytest_asyncio.fixture
async def dataflow_job_state(dataflow_job_id: str):
    # NOTE: much of this test is redundant with dataflow integration test
    #    https://github.com/pangeo-forge/pangeo-forge-runner/
    #    blob/c7c5e88c006ce5f5ea636d061423981bb9d23734/tests/integration/test_dataflow_integration.py

    # 6 minutes seems like an average runtime for these jobs, but being optimistic
    # let's start by waiting 5 minutes
    start = time.time()
    utc_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(start))
    print(f"Waiting for 5 mins, starting at {utc_time = }")
    time.sleep(60 * 5)
    # at this point, the job has been submitted and we know the job_id, so time to start polling
    # dataflow to see if its completed.
    show_job = f"gcloud dataflow jobs show {dataflow_job_id} --format=json".split()
    while True:
        elapsed = time.time() - start
        print(f"Time {elapsed = }")
        if elapsed > 60 * 12:
            pytest.fail(f"Time {elapsed = } on running job.")

        # check job state
        state_proc = subprocess.run(show_job, capture_output=True)
        assert state_proc.returncode == 0
        state = json.loads(state_proc.stdout)["state"]
        print(f"Current {state = }")
        if state == "Done":
            # on Dataflow, "Done" means success
            break
        elif state == "Running":
            # still running, let's give it another 30s then check again
            await asyncio.sleep(30)
        else:
            # consider any other state a failure
            pytest.fail(f"{state = } is neither 'Done' nor 'Running'")
    # if we get here without failing out, the yielded state should be 'Done'
    yield state


@pytest_asyncio.fixture
async def job_status_notification_comment_body(
    gh: GitHubAPI,
    gh_kws: dict,
    base: str,
    recipe_pr: dict,
    dataflow_job_state: str,
):
    # this value is not actually used below, but we include it as a fixture
    # here to preserve the desired inheritance path of fixtures in this module
    assert dataflow_job_state == "Done"

    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > 60 * 5:
            pytest.fail(f"Time {elapsed = } waiting for job success notification comment.")

        comments = await gh.getitem(
            f"/repos/{base}/issues/{recipe_pr['number']}/comments",
            **gh_kws,
        )
        if comments:
            last_comment_body: str = comments[-1]["body"]
            if not last_comment_body.startswith("/run"):
                break

        else:
            await asyncio.sleep(15)

    yield last_comment_body


@pytest.mark.asyncio
async def test_end_to_end_integration(
    job_status_notification_comment_body: str,
    recipe_pr: dict,
    recipe_id: str,
):
    assert job_status_notification_comment_body.startswith(
        f":tada: The test run of `{recipe_id}` at {recipe_pr['head']['sha']} succeeded!"
    )
