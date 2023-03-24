import hashlib
import hmac
import json
import os
import secrets
import subprocess
from collections.abc import AsyncGenerator
from typing import Literal, Optional, TypedDict, Union

import httpx
import pytest
import pytest_asyncio
import pytest_mock
import yaml  # type: ignore
from asgi_lifespan import LifespanManager
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.api import app
from pangeo_forge_orchestrator.routers.github_app import get_http_session


@pytest.fixture(autouse=True, scope="session")
def setup_and_teardown(
    session_mocker,
    mock_app_config_path,
    mock_secrets_dir,
    mock_bakeries_dir,
):
    def get_mock_app_config_path():
        return mock_app_config_path

    def get_mock_secrets_dir():
        return mock_secrets_dir

    def get_mock_bakeries_dir():
        return mock_bakeries_dir

    session_mocker.patch.object(
        pangeo_forge_orchestrator.config,
        "get_app_config_path",
        get_mock_app_config_path,
    )
    session_mocker.patch.object(
        pangeo_forge_orchestrator.config,
        "get_secrets_dir",
        get_mock_secrets_dir,
    )
    session_mocker.patch.object(
        pangeo_forge_orchestrator.config,
        "get_bakeries_dir",
        get_mock_bakeries_dir,
    )
    session_mocker.patch.dict(
        os.environ,
        {"PANGEO_FORGE_DEPLOYMENT": "pytest-deployment"},
    )
    yield
    # teardown here (none for now)


# GitHub App Fixtures -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rsa_key_pair():
    """Simulates keys generated for the GitHub App. See https://stackoverflow.com/a/39126754."""

    key = rsa.generate_private_key(
        backend=crypto_default_backend(), public_exponent=65537, key_size=2048
    )
    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.PKCS8,
        crypto_serialization.NoEncryption(),
    )
    public_key = key.public_key().public_bytes(
        crypto_serialization.Encoding.OpenSSH, crypto_serialization.PublicFormat.OpenSSH
    )
    return [k.decode(encoding="utf-8") for k in (private_key, public_key)]


@pytest.fixture(scope="session")
def private_key(rsa_key_pair):
    """Convenience fixture so we don't have to unpack ``rsa_key_pair`` in every test function."""

    private_key, _ = rsa_key_pair
    return private_key


@pytest.fixture(scope="session")
def webhook_secret():
    return secrets.token_hex(20)


@pytest.fixture(scope="session")
def mock_config_kwargs(webhook_secret, private_key):
    return {
        "github_app": {
            "id": 1234567,
            "app_name": "pytest-mock-github-app",
            "webhook_url": "https://api.pangeo-forge.org/github/hooks",  # TODO: fixturize
            "webhook_secret": webhook_secret,
            "private_key": private_key,
        },
    }


@pytest.fixture(scope="session")
def mock_secrets_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("secrets")


@pytest.fixture(scope="session")
def mock_app_config_path(mock_config_kwargs, mock_secrets_dir):
    """ """
    path = mock_secrets_dir / "config.pytest-deployment.yaml"
    with open(path, "w") as f:
        yaml.dump(mock_config_kwargs, f)

    return path


@pytest.fixture(scope="session")
def mock_bakeries_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("bakeries")


@pytest.fixture(scope="session", autouse=True)
def mock_bakeries_config_paths(mock_bakeries_dir):
    """ """
    path = mock_bakeries_dir / "pangeo-ldeo-nsf-earthcube.pytest-deployment.yaml"
    kws = dict(
        Bake=dict(
            bakery_class="foo",
        ),
        TargetStorage=dict(
            fsspec_class="bar",
            fsspec_args={},
            root_path="baz",
            public_url="https://public-endpoint.org/bucket-name/",
        ),
        InputCacheStorage=dict(
            fsspec_class="bar",
            fsspec_args={},
            root_path="baz",
        ),
        MetadataCacheStorage=dict(
            fsspec_class="bar",
            fsspec_args={},
            root_path="baz",
        ),
    )
    with open(path, "w") as f:
        yaml.dump(kws, f)

    return [str(path)]  # TODO: test with > 1 bakery


@pytest.fixture(scope="session")
def mock_secret_bakery_args_paths(mock_secrets_dir):
    """ """
    path = mock_secrets_dir / "bakery-args.pangeo-ldeo-nsf-earthcube.yaml"
    kws = dict()  # TODO: actually pass some values
    with open(path, "w") as f:
        yaml.dump(kws, f)

    return [str(path)]  # TODO: test with > 1 bakery env


# For this general pattern, see
# https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html
# which is adjustmented according to https://stackoverflow.com/a/73019163.
# And for LifespanManager, see https://github.com/tiangolo/fastapi/issues/2003#issuecomment-801140731.
@pytest_asyncio.fixture
async def async_app_client():
    async with AsyncClient(app=app, base_url="http://test") as client, LifespanManager(app):
        yield client


@pytest.fixture(params=["https://api.pangeo-forge.org", "https://api-staging.pangeo-forge.org"])
def api_url(request):
    return request.param


@pytest.fixture
def app_hook_config_url(api_url):
    return f"{api_url}/github/hooks/"


@pytest.fixture
def staged_recipes_pr_1_files():
    return [
        {
            "filename": "recipes/new-dataset/recipe.py",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/staged-recipes/"
                "contents/recipes/new-dataset/recipe.py"
            ),
            "sha": "abcdefg",
        },
        {
            "filename": "recipes/new-dataset/meta.yaml",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/staged-recipes/"
                "contents/recipes/new-dataset/meta.yaml"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def staged_recipes_pr_2_files(staged_recipes_pr_1_files):
    # This PR is the automated cleanup PR following merge of PR 1. I think that means the
    # `files` JSON is more-or-less the same? Except that the contents would be different,
    # of course, but our fixtures don't capture that level of detail yet.
    return staged_recipes_pr_1_files


@pytest.fixture
def staged_recipes_pr_3_files():
    return [
        {
            "filename": "README.md",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/staged-recipes/"
                "contents/README.md"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def staged_recipes_pr_4_files():
    return [
        {
            "filename": "README.md",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/dataset-feedstock/"
                "contents/README.md"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def staged_recipes_pr_5_files():
    return [
        {
            "filename": "recipes/new-dataset/recipe.py",
            "contents_url": (
                "https://api.github.com/repos/contributor-username/staged-recipes/"
                "contents/recipes/new-dataset/recipe.py"
            ),
            "sha": "abcdefg",
        },
    ]


@pytest.fixture
def staged_recipes_pulls_files(
    staged_recipes_pr_1_files,
    staged_recipes_pr_2_files,
    staged_recipes_pr_3_files,
    staged_recipes_pr_4_files,
    staged_recipes_pr_5_files,
):
    return {
        1: staged_recipes_pr_1_files,
        2: staged_recipes_pr_2_files,
        3: staged_recipes_pr_3_files,
        4: staged_recipes_pr_4_files,
        5: staged_recipes_pr_5_files,
    }


##################


class EventRequest(TypedDict):
    headers: dict
    payload: Union[str, dict]  # union because of dataflow payload edge case


def add_hash_signature(request: EventRequest, webhook_secret: str) -> EventRequest:
    if request["headers"]["X-GitHub-Event"] != "dataflow":
        payload_bytes = bytes(json.dumps(request["payload"]), "utf-8")
    else:
        # special case for dataflow payload, to replicate how it is actually sent.
        # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
        # for further detail. ideally, this special casing wll be removed eventually.
        payload_bytes = request["payload"].encode("utf-8")  # type: ignore

    hash_signature = hmac.new(
        bytes(webhook_secret, encoding="utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    request["headers"].update({"X-Hub-Signature-256": f"sha256={hash_signature}"})
    return request


class MockHttpResponses(TypedDict, total=False):
    GET: Optional[httpx.Response]
    POST: Optional[httpx.Response]
    PATCH: Optional[httpx.Response]
    PUT: Optional[httpx.Response]
    DELETE: Optional[httpx.Response]


def make_mock_httpx_client(mock_responses: dict[str, MockHttpResponses]):
    async def handler(request: httpx.Request):
        method: Literal["GET", "POST", "PATCH", "PUT", "DELETE"] = request.method
        return mock_responses[request.url.path][method]

    mounts = {"https://api.github.com": httpx.MockTransport(handler)}

    return httpx.AsyncClient(mounts=mounts)


@pytest_asyncio.fixture(
    params=[
        dict(
            number=1,
            base_repo_full_name="pangeo-forge/staged-recipes",
            title="Add XYZ awesome dataset",
            head_sha="abc",
        ),
    ],
)
async def recipe_pr(
    webhook_secret: str,
    request: pytest.FixtureRequest,
    mocker: pytest_mock.MockerFixture,
    async_app_client: httpx.AsyncClient,
) -> AsyncGenerator[tuple[dict, httpx.AsyncClient], None]:
    fixture_request = request  # disambiguate with a more specific name
    headers = {"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "123-456-789"}
    payload = {
        "action": "synchronize",
        "pull_request": {
            "number": fixture_request.param["number"],
            "base": {
                "repo": {
                    "html_url": f"https://github.com/{fixture_request.param['base_repo_full_name']}",
                    "url": f"https://api.github.com/repos/{fixture_request.param['base_repo_full_name']}",
                    "full_name": fixture_request.param["base_repo_full_name"],
                },
            },
            "head": {
                "repo": {
                    "html_url": "https://github.com/contributor-username/staged-recipes",
                    "url": "https://api.github.com/repos/contributor-username/staged-recipes",
                },
                "sha": fixture_request.param["head_sha"],
            },
            "labels": [],
            "title": fixture_request.param["title"],
        },
    }
    mock_github_webhook = add_hash_signature(
        {"headers": headers, "payload": payload}, webhook_secret
    )

    # setup mock github backend for this test

    mock_github_responses = {
        "/app/installations": MockHttpResponses(
            GET=httpx.Response(200, json=[{"id": 1234567}]),
        ),
        f"/app/installations/{1234567}/access_tokens": MockHttpResponses(
            POST=httpx.Response(200, json={"token": "abcdefghijklmnop"}),
        ),
        "/repos/pangeo-forge/staged-recipes/check-runs": MockHttpResponses(
            POST=httpx.Response(200, json={"id": 1234567890})
        ),
        "/repos/pangeo-forge/staged-recipes/pulls/1/files": MockHttpResponses(
            GET=httpx.Response(
                200,
                json=[
                    {
                        "filename": "recipes/new-dataset/recipe.py",
                        "contents_url": (
                            "https://api.github.com/repos/contributor-username/staged-recipes/"
                            "contents/recipes/new-dataset/recipe.py"
                        ),
                        "sha": "abcdefg",
                    },
                    {
                        "filename": "recipes/new-dataset/meta.yaml",
                        "contents_url": (
                            "https://api.github.com/repos/contributor-username/staged-recipes/"
                            "contents/recipes/new-dataset/meta.yaml"
                        ),
                        "sha": "abcdefg",
                    },
                ],
            )
        ),
        "/repos/pangeo-forge/staged-recipes/check-runs/1234567890": MockHttpResponses(
            PATCH=httpx.Response(200),
        ),
    }

    def get_mock_http_session():
        return make_mock_httpx_client(mock_github_responses)

    # https://fastapi.tiangolo.com/advanced/testing-dependencies/#testing-dependencies-with-overrides
    app.dependency_overrides[get_http_session] = get_mock_http_session

    def mock_subprocess_check_output(cmd: list[str]):
        return (
            '{"message": "Picked Git content provider.\\n", "status": "fetching"}\n'
            '{"message": "Cloning into \'/var/folders/tt/4f941hdn0zq549zdwhcgg98c0000gn/T/tmp10gezh_p\'...\\n", "status": "fetching"}\n'
            '{"message": "HEAD is now at 0fd9b13 Update foo.txt\\n", "status": "fetching"}\n'
            '{"message": "Expansion complete", "status": "completed", "meta": {"title": "Global Precipitation Climatology Project", "description": "Global Precipitation Climatology Project (GPCP) Daily Version 1.3 gridded, merged ty satellite/gauge precipitation Climate data Record (CDR) from 1996 to present.\\n", "pangeo_forge_version": "0.9.0", "pangeo_notebook_version": "2022.06.02", "recipes": [{"id": "gpcp", "object": "recipe:recipe"}], "provenance": {"providers": [{"name": "NOAA NCEI", "description": "National Oceanographic & Atmospheric Administration National Centers for Environmental Information", "roles": ["host", "licensor"], "url": "https://www.ncei.noaa.gov/products/global-precipitation-climatology-project"}, {"name": "University of Maryland", "description": "University of Maryland College Park Earth System Science Interdisciplinary Center (ESSIC) and Cooperative Institute for Climate and Satellites (CICS).\\n", "roles": ["producer"], "url": "http://gpcp.umd.edu/"}], "license": "No constraints on data access or use."}, "maintainers": [{"name": "Ryan Abernathey", "orcid": "0000-0001-5999-4917", "github": "rabernat"}], "bakery": {"id": "pangeo-ldeo-nsf-earthcube"}}}\n'
        )

    mocker.patch.object(subprocess, "check_output", mock_subprocess_check_output)

    webhook_response = await async_app_client.post(
        "/github/hooks/",
        json=mock_github_webhook["payload"],
        headers=mock_github_webhook["headers"],
    )
    assert webhook_response.status_code == 202

    # there are two layers of github mocking: one for the routes accessed by the app itself (above).
    # and another for routes that the tests need to access to make assertions against, here:
    mock_gh_responses_for_pytest = {
        (
            f"/repos/{fixture_request.param['base_repo_full_name']}"
            f"/commits/{fixture_request.param['head_sha']}/check-runs"
        ): MockHttpResponses(
            GET=httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "check_runs": [
                        {
                            "name": "Parse meta.yaml",
                            "head_sha": fixture_request.param["head_sha"],
                            "status": "completed",
                            "started_at": "2022-08-11T21:22:51Z",
                            "output": {
                                "title": "Recipe runs queued for latest commit",
                                "summary": "",
                            },
                            "details_url": "https://pangeo-forge.org/",
                            "id": 0,
                            "conclusion": "success",
                            "completed_at": "2022-08-11T21:22:51Z",
                        }
                    ],
                },
            )
        ),
    }

    yield fixture_request.param, make_mock_httpx_client(mock_gh_responses_for_pytest)

    # cleanup overrides set above
    app.dependency_overrides = {}
    assert not app.dependency_overrides
