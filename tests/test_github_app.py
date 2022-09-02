import hashlib
import hmac
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Union

import jwt
import pytest
from sqlalchemy.orm.exc import NoResultFound

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.http import HttpSession, http_session
from pangeo_forge_orchestrator.routers.github_app import (
    get_access_token,
    get_app_webhook_url,
    get_jwt,
    get_repo_id,
    html_to_api_url,
    html_url_to_repo_full_name,
    list_accessible_repos,
)


def mock_access_token_from_jwt(jwt: str):
    """Certain GitHub API actions are authenticated via JWT and others are authenticated with an
    access token. For the latter case, we exchange a JWT to obtain an access token. The code in
    this function is almost definitely not how that works on GitHub's backend, but for the purposes
    of testing, it simulates the process of exchanging one token for another. All GitHub access
    tokens appear to begin with ``'ghs_'``, so we replicate that here for realism.
    """

    sha256 = hashlib.sha256(bytes(jwt, encoding="utf-8")).hexdigest()[:36]
    return f"ghs_{sha256}"


@dataclass
class _MockGitHubBackend:
    _app_hook_config_url: str
    _accessible_repos: List[dict]
    _app_hook_deliveries: List[dict]
    _app_installations: List[dict]
    _check_runs: List[dict]


@dataclass
class MockGitHubAPI:
    http_session: HttpSession
    username: str

    # ``_backend`` is not part of the actual GitHubAPI interface which this object mocks.
    # it is added here so that we have a way to persist data throughout the test session.
    _backend: _MockGitHubBackend

    async def getitem(
        self,
        path: str,
        accept: Optional[str] = None,
        jwt: Optional[str] = None,
        oauth_token: Optional[str] = None,
    ) -> Union[dict, List[dict]]:
        if path == "/app/hook/config":
            return {"url": self._backend._app_hook_config_url}
        elif path.startswith("/repos/"):
            if "/commits/" in path and path.endswith("/check-runs"):
                # mocks getting a check run from the github api
                commit_sha = path.split("/commits/")[-1].split("/check-runs")[0]
                check_runs = [c for c in self._backend._check_runs if c["head_sha"] == commit_sha]
                return {"total_count": len(check_runs), "check_runs": check_runs}
            else:
                # mocks getting a github repo id. see ``routers.github_app::get_repo_id``
                return {"id": 123456789}  # TODO: assign dynamically from _MockGitHubBackend
        elif path == "/installation/repositories":
            return {"repositories": self._backend._accessible_repos}
        elif path.startswith("/app/hook/deliveries/"):
            id_ = int(path.replace("/app/hook/deliveries/", ""))
            return [
                {"response": d} for d in self._backend._app_hook_deliveries if d["id"] == id_
            ].pop(0)
        elif "pulls" in path and path.endswith("files"):
            return [{"filename": "recipes/new-dataset/recipe.py"}]
        else:
            raise NotImplementedError(f"Path '{path}' not supported.")

    async def getiter(
        self,
        path: str,
        accept: Optional[str] = None,
        jwt: Optional[str] = None,
    ):
        if path == "/app/hook/deliveries":
            for delivery in self._backend._app_hook_deliveries:
                yield delivery
        elif path == "/app/installations":
            for installation in self._backend._app_installations:
                yield installation
        else:
            raise NotImplementedError(f"Path '{path}' not supported.")

    async def post(
        self,
        path: str,
        data: dict,
        accept: Optional[str] = None,
        jwt: Optional[str] = None,
        oauth_token: Optional[str] = None,
    ):
        if path.endswith("/check-runs"):
            # create a new check run
            id_ = len(self._backend._check_runs)
            new_check_run = data | {"id": id_}  # type: ignore
            self._backend._check_runs.append(new_check_run)
            return new_check_run
        elif path.startswith("/app/installations/") and path.endswith("/access_tokens"):
            # https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app
            # We can't get a JWT without our private key. If we didn't have these checks here, and the
            # key was missing, we would get an error in the call to ``get_jwt``, but checking for the
            # private_key here allows us to catch errors faster, and more clearly illustrates the
            # relationship of these secrets in the tests.
            private_key = os.environ["PEM_FILE"]
            assert private_key is not None
            assert private_key.startswith("-----BEGIN PRIVATE KEY-----")
            return {"token": mock_access_token_from_jwt(jwt=get_jwt())}
        else:
            raise NotImplementedError(f"Path '{path}' not supported.")

    async def patch(self, path: str, oauth_token: str, accept: str, data: dict):
        if "/check-runs/" in path and not path.endswith("/check-runs/"):
            id_ = int(path.split("/check-runs/")[-1])
            # In the mock ``.post`` method for the "/check-runs" path above, we add check runs
            # sequentially, so we (should) be able to index the self._backend._check_runs list like this.
            # This is shorthand for the mock. In reality, the GitHub check runs ids are longer,
            # non-sequential integers.
            self._backend._check_runs[id_].update(data)
            return self._backend._check_runs[id_]
        else:
            raise NotImplementedError(f"Path '{path}' not supported.")


@pytest.fixture
def api_url():
    """In production, this might be configured to point to a different url, for example for
    testing new features on a review deployment."""

    return "https://api.pangeo-forge.org"


@pytest.fixture
def app_hook_config_url(api_url):
    return f"{api_url}/github/hooks/"


@pytest.fixture
def accessible_repos():
    """The repositories in which the app has been installed."""

    return [{"full_name": "pangeo-forge/staged-recipes"}]


@pytest.fixture
def app_hook_deliveries():
    """Webhook deliveries to the GitHub App. Examples copied from real delivieres to the app."""

    return [
        {
            "id": 24081517883,
            "guid": "04d4b7f0-0f85-11ed-8539-b846a7d005af",
            "delivered_at": "2022-07-29T21:25:50Z",
            "redelivery": "false",
            "duration": 0.03,
            "status": "Invalid HTTP Response: 501",
            "status_code": 501,
            "event": "check_suite",
            "action": "requested",
            "installation_id": 27724604,
            "repository_id": 518221894,
            "url": "",
        },
        {
            "id": 24081517383,
            "guid": "04460c80-0f85-11ed-8fc2-f8b6d8b7d25d",
            "delivered_at": "2022-07-29T21:25:50Z",
            "redelivery": "false",
            "duration": 0.04,
            "status": "OK",
            "status_code": 202,
            "event": "pull_request",
            "action": "synchronize",
            "installation_id": 27724604,
            "repository_id": 518221894,
            "url": "",
        },
    ]


@pytest.fixture
def app_installations():
    """Installations for the mock GitHub App. The real payload contains a lot more information, but
    just including the subset that we use here.
    """

    return [{"id": 1234567}]


@pytest.fixture
def mock_github_backend(
    app_hook_config_url,
    accessible_repos,
    app_hook_deliveries,
    app_installations,
):
    """The backend data which simulates data that is retrievable via the GitHub API. Importantly,
    this has to be its own fixture, so that if multiple instances of the ``MockGitHubAPI`` are
    used within a single test invocation, each of these sessions share a single instance of the
    backend data. Multiple ``MockGitHubAPI`` sessions *are* used in certain test invocations,
    because sometimes we use one session to populate pre-requisite data, and then the function
    under test starts a separate session to query that data.
    """

    backend_kws = {
        "_app_hook_config_url": app_hook_config_url,
        "_accessible_repos": accessible_repos,
        "_app_hook_deliveries": app_hook_deliveries,
        "_app_installations": app_installations,
        "_check_runs": list(),
    }
    return _MockGitHubBackend(**backend_kws)


@pytest.fixture
def get_mock_github_session(mock_github_backend):
    def _get_mock_github_session(http_session: HttpSession):
        return MockGitHubAPI(http_session, "pangeo-forge", _backend=mock_github_backend)

    return _get_mock_github_session


def test_get_github_session(mocker, get_mock_github_session):
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    from pangeo_forge_orchestrator.routers.github_app import get_github_session

    gh = get_github_session(http_session)
    assert isinstance(gh, MockGitHubAPI)


@pytest.mark.parametrize(
    "html_url,expected_api_url",
    (
        [
            "https://github.com/pangeo-forge/staged-recipes",
            "https://api.github.com/repos/pangeo-forge/staged-recipes",
        ],
    ),
)
def test_html_to_api_url(html_url, expected_api_url):
    actual_api_url = html_to_api_url(html_url)
    assert actual_api_url == expected_api_url


@pytest.mark.parametrize(
    "html_url,expected_repo_full_name",
    (["https://github.com/pangeo-forge/staged-recipes", "pangeo-forge/staged-recipes"],),
)
def test_html_url_to_repo_full_name(html_url, expected_repo_full_name):
    actual_repo_full_name = html_url_to_repo_full_name(html_url)
    assert actual_repo_full_name == expected_repo_full_name


def test_get_jwt(rsa_key_pair):
    _, public_key = rsa_key_pair
    encoded_jwt = get_jwt()
    decoded = jwt.decode(encoded_jwt, public_key, algorithms=["RS256"])
    assert list(decoded.keys()) == ["iat", "exp", "iss"]
    assert all([isinstance(v, int) for v in decoded.values()])


@pytest.mark.asyncio
async def test_get_access_token(private_key, get_mock_github_session):
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    token = await get_access_token(mock_gh)
    assert token.startswith("ghs_")
    assert len(token) == 40  # "ghs_" (4 chars) + 36 character token


@pytest.mark.asyncio
async def test_get_app_webhook_url(private_key, get_mock_github_session):
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    url = await get_app_webhook_url(mock_gh)
    assert url == "https://api.pangeo-forge.org/github/hooks/"


@pytest.fixture
def check_run_create_kwargs():
    return dict(
        name="synchronize",
        head_sha="abcdefg",  # TODO: fixturize
        status="in_progress",
        started_at=f"{datetime.utcnow().replace(microsecond=0).isoformat()}Z",
        output=dict(
            title="Syncing latest commit to Pangeo Forge Cloud",
            summary="",  # required
        ),
        details_url="https://pangeo-forge.org/",  # TODO: make this more specific.
    )


@pytest.mark.parametrize("repo_full_name", ["pangeo-forge/staged-recipes"])
@pytest.mark.asyncio
async def test_get_repo_id(private_key, get_mock_github_session, repo_full_name):
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    repo_id = await get_repo_id(repo_full_name, mock_gh)
    assert isinstance(repo_id, int)


@pytest.mark.asyncio
async def test_list_accessible_repos(private_key, get_mock_github_session, accessible_repos):
    os.environ["PEM_FILE"] = private_key
    mock_gh = get_mock_github_session(http_session)
    repos = await list_accessible_repos(mock_gh)
    assert repos == [r["full_name"] for r in accessible_repos]


@pytest.mark.asyncio
async def test_get_deliveries(
    mocker,
    private_key,
    get_mock_github_session,
    app_hook_deliveries,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    response = await async_app_client.get("/github/hooks/deliveries")
    assert response.status_code == 200
    assert response.json() == app_hook_deliveries


@pytest.mark.asyncio
async def test_get_delivery(
    mocker,
    private_key,
    get_mock_github_session,
    app_hook_deliveries,
    async_app_client,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    for delivery in app_hook_deliveries:
        id_ = delivery["id"]
        response = await async_app_client.get(f"/github/hooks/deliveries/{id_}")
        assert response.status_code == 200
        assert response.json() == delivery


@pytest.mark.asyncio
async def test_get_feedstock_check_runs(
    mocker,
    private_key,
    get_mock_github_session,
    check_run_create_kwargs,
    async_app_client,
    admin_key,
):
    os.environ["PEM_FILE"] = private_key
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )

    # populate the pangeo forge database with a feedstock
    admin_headers = {"X-API-Key": admin_key}
    fstock_response = await async_app_client.post(
        "/feedstocks/",
        json={"spec": "pangeo-forge/staged-recipes"},  # TODO: set dynamically
        headers=admin_headers,
    )
    assert fstock_response.status_code == 200
    fstock_id = fstock_response.json()["id"]

    # populate mock github backend with check runs for the feedstock (only 1 for now)
    mock_gh = get_mock_github_session(http_session)
    check_run_response = await mock_gh.post(
        "/repos/pangeo-forge/staged-recipes/check-runs",
        data=check_run_create_kwargs,
    )
    commit_sha = check_run_response["head_sha"]

    # now that the data is in the mock github backend, retrieve it
    response = await async_app_client.get(
        f"/feedstocks/{fstock_id}/commits/{commit_sha}/check-runs"
    )
    json_ = response.json()
    assert json_["total_count"] == 1  # this value represents the number of check runs created
    for k in check_run_create_kwargs:
        assert json_["check_runs"][0][k] == check_run_create_kwargs[k]


@pytest.mark.parametrize(
    "hash_signature_problem,expected_response_detail",
    [
        ("missing", "Request does not include a GitHub hash signature header."),
        ("incorrect", "Request hash signature invalid."),
    ],
)
@pytest.mark.asyncio
async def test_receive_github_hook_unauthorized(
    async_app_client,
    hash_signature_problem,
    expected_response_detail,
):
    if hash_signature_problem == "missing":
        headers = {}
    elif hash_signature_problem == "incorrect":
        os.environ["GITHUB_WEBHOOK_SECRET"] = "foobar"
        headers = {"X-Hub-Signature-256": "abcdefg"}

    response = await async_app_client.post(
        "/github/hooks/",
        json={},
        headers=headers,
    )
    assert response.status_code == 401
    assert json.loads(response.text)["detail"] == expected_response_detail


def mock_subprocess_check_output(cmd: List[str]):
    """ """

    if cmd[0] == "pangeo-forge-runner":
        if cmd[1] == "expand-meta":
            # As a first step, we are not accounting for any arguments passed to expand-meta.
            # This return value was obtained by running, with pangeo-forge-runner==0.3
            #  ```
            #  subprocess.check_output(
            #      "pangeo-forge-runner expand-meta --repo https://github.com/pangeo-forge/github-app-sandbox-repository --ref 0fd9b13f0d718772e78fc2b53fd7e9da82a522f3 --json".split()
            #  )
            #  ```
            return (
                '{"message": "Picked Git content provider.\\n", "status": "fetching"}\n'
                '{"message": "Cloning into \'/var/folders/tt/4f941hdn0zq549zdwhcgg98c0000gn/T/tmp10gezh_p\'...\\n", "status": "fetching"}\n'
                '{"message": "HEAD is now at 0fd9b13 Update foo.txt\\n", "status": "fetching"}\n'
                '{"message": "Expansion complete", "status": "completed", "meta": {"title": "Global Precipitation Climatology Project", "description": "Global Precipitation Climatology Project (GPCP) Daily Version 1.3 gridded, merged ty satellite/gauge precipitation Climate data Record (CDR) from 1996 to present.\\n", "pangeo_forge_version": "0.9.0", "pangeo_notebook_version": "2022.06.02", "recipes": [{"id": "gpcp", "object": "recipe:recipe"}], "provenance": {"providers": [{"name": "NOAA NCEI", "description": "National Oceanographic & Atmospheric Administration National Centers for Environmental Information", "roles": ["host", "licensor"], "url": "https://www.ncei.noaa.gov/products/global-precipitation-climatology-project"}, {"name": "University of Maryland", "description": "University of Maryland College Park Earth System Science Interdisciplinary Center (ESSIC) and Cooperative Institute for Climate and Satellites (CICS).\\n", "roles": ["producer"], "url": "http://gpcp.umd.edu/"}], "license": "No constraints on data access or use."}, "maintainers": [{"name": "Ryan Abernathey", "orcid": "0000-0001-5999-4917", "github": "rabernat"}], "bakery": {"id": "pangeo-ldeo-nsf-earthcube"}}}\n'
            )
        else:
            raise NotImplementedError(f"Command {cmd} not implemented in tests.")
    else:
        raise NotImplementedError(
            f"Command {cmd} does not begin with 'pangeo-forge-runner'. Currently, "
            "'pangeo-forge-runner' is the only command line mock implemented."
        )


@pytest.fixture
def synchronize_request():
    headers = {"X-GitHub-Event": "pull_request"}
    payload = {
        "action": "synchronize",
        "pull_request": {
            "number": 1,
            "base": {
                "repo": {
                    "html_url": "https://github.com/pangeo-forge/staged-recipes",
                    "url": "https://api.github.com/repos/pangeo-forge/staged-recipes",
                    "full_name": "pangeo-forge/staged-recipes",
                },
            },
            "head": {
                "repo": {
                    "html_url": "https://github.com/contributor-username/staged-recipes",
                    "url": "https://api.github.com/repos/contributor-username/staged-recipes",
                },
                "sha": "abc",
            },
            "labels": [],
            "title": "Add XYZ awesome dataset",
        },
    }
    return {"headers": headers, "payload": payload}


@pytest.fixture(
    scope="session",
    params=[
        pytest.lazy_fixture("synchronize_request"),
    ],
)
def github_webhook_request(request, webhook_secret):
    """ """

    payload_bytes = bytes(json.dumps(request.param["payload"]), "utf-8")
    hash_signature = hmac.new(
        bytes(webhook_secret, encoding="utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    request.param["headers"].update({"X-Hub-Signature-256": f"sha256={hash_signature}"})

    return request.param


@pytest.mark.parametrize("raises_database_dependencies_error", [True, False])
@pytest.mark.asyncio
async def test_receive_github_hook(
    mocker,
    get_mock_github_session,
    webhook_secret,
    async_app_client,
    github_webhook_request,
    private_key,
    raises_database_dependencies_error,
    admin_key,
):
    os.environ["GITHUB_WEBHOOK_SECRET"] = webhook_secret
    mocker.patch.object(
        pangeo_forge_orchestrator.routers.github_app,
        "get_github_session",
        get_mock_github_session,
    )
    mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)
    # PEM_FILE is used to authenticate with github in background tasks
    os.environ["PEM_FILE"] = private_key

    if raises_database_dependencies_error:
        with pytest.raises(NoResultFound):
            response = await async_app_client.post(
                "/github/hooks/",
                json=github_webhook_request["payload"],
                headers=github_webhook_request["headers"],
            )
    else:
        # In order for the recipe run creation process to succeed, both the bakery and feedstock
        # specified in the meta.yaml must already exist in the database.
        admin_headers = {"X-API-Key": admin_key}
        bakery_create_response = await async_app_client.post(
            "/bakeries/",
            json={  # TODO: set dynamically
                "region": "us-central1",
                "name": "pangeo-ldeo-nsf-earthcube",
                "description": "A great bakery to test with!",
            },
            headers=admin_headers,
        )
        assert bakery_create_response.status_code == 200

        # FIXME: the database *should* be empty before the test? but for some reason that's not
        # happening. so just hack around it for now, like this:
        existing_feedstocks = await async_app_client.get("/feedstocks/")
        existing_matching = [
            f for f in existing_feedstocks.json() if f["spec"] == "pangeo-forge/staged-recipes"
        ]
        if not existing_matching:
            feedstock_create_response = await async_app_client.post(
                "/feedstocks/",
                json={"spec": "pangeo-forge/staged-recipes"},  # TODO: set dynamically
                headers=admin_headers,
            )
            assert feedstock_create_response.status_code == 200
            fstock_id = feedstock_create_response.json()["id"]
        else:
            fstock_id = existing_matching[0]["id"]

        # Now that the database is pre-populated with pre-requisites, we can actually test.
        response = await async_app_client.post(
            "/github/hooks/",
            json=github_webhook_request["payload"],
            headers=github_webhook_request["headers"],
        )
        assert response.status_code == 202

        # first assert that the recipe runs were created as expected
        recipe_runs_response = await async_app_client.get("/recipe_runs/")
        assert recipe_runs_response.status_code == 200
        # TODO: fixturize expected_recipe_runs_response
        expected_recipe_runs_response = [
            {
                "recipe_id": "gpcp",
                "bakery_id": 1,
                "feedstock_id": 1,
                "head_sha": "abc",
                "version": "",
                "started_at": "2022-08-11T21:03:56",
                "completed_at": None,
                "conclusion": None,
                "status": "queued",
                "is_test": True,
                "dataset_type": "zarr",
                "dataset_public_url": None,
                "message": None,
                "id": 1,
            }
        ]
        for k in expected_recipe_runs_response[0]:
            if not k == "started_at" and not k == "completed_at":
                assert expected_recipe_runs_response[0][k] == recipe_runs_response.json()[0][k]

        # then assert that the check runs were created as expected
        commit_sha = recipe_runs_response.json()[0]["head_sha"]
        check_runs_response = await async_app_client.get(
            f"/feedstocks/{fstock_id}/commits/{commit_sha}/check-runs"
        )
        # TODO: fixturize expected_check_runs_response
        expected_check_runs_response = {
            "total_count": 1,
            "check_runs": [
                {
                    "name": "synchronize",
                    "head_sha": "abc",
                    "status": "completed",
                    "started_at": "2022-08-11T21:22:51Z",
                    "output": {
                        "title": "Recipe runs queued for latest commit",
                        "summary": "Recipe runs created at commit `abc`:\n- https://pangeo-forge.org/dashboard/recipe-run/1?feedstock_id=1",
                    },
                    "details_url": "https://pangeo-forge.org/",
                    "id": 0,
                    "conclusion": "success",
                    "completed_at": "2022-08-11T21:22:51Z",
                }
            ],
        }
        assert expected_check_runs_response["total_count"] == 1
        for k in expected_check_runs_response["check_runs"][0]:
            if not k == "started_at" and not k == "completed_at":
                assert (
                    expected_check_runs_response["check_runs"][0][k]
                    == check_runs_response.json()["check_runs"][0][k]
                )

        # Teardown. TODO: move this into a fixture, with a teardown block after `yield`.
        # If we don't delete, they'll persist in session-scoped database, and mess up other tests.
        # NOTE: Must delete recipe runs first, otherwise null-pointing foreign keys cause errors.
        for r in recipe_runs_response.json():
            delete_response = await async_app_client.delete(
                f"/recipe_runs/{r['id']}",
                headers=admin_headers,
            )
            assert delete_response.status_code == 200

        bakery_delete_response = await async_app_client.delete(
            f"/bakeries/{bakery_create_response.json()['id']}",
            headers=admin_headers,
        )
        assert bakery_delete_response.status_code == 200
        feedstock_delete_response = await async_app_client.delete(
            f"/feedstocks/{fstock_id}",
            headers=admin_headers,
        )
        assert feedstock_delete_response.status_code == 200
