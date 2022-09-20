import hashlib
import hmac
import json

import pytest

from pangeo_forge_orchestrator.http import HttpSession

from .mock_gidgethub import MockGitHubAPI, _MockGitHubBackend


def add_hash_signature(request: dict, webhook_secret: str):
    if request["headers"]["X-GitHub-Event"] != "dataflow":
        payload_bytes = bytes(json.dumps(request["payload"]), "utf-8")
    else:
        # special case for dataflow payload, to replicate how it is actually sent.
        # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
        # for further detail. ideally, this special casing wll be removed eventually.
        payload_bytes = request["payload"].encode("utf-8")

    hash_signature = hmac.new(
        bytes(webhook_secret, encoding="utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    request["headers"].update({"X-Hub-Signature-256": f"sha256={hash_signature}"})
    return request


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
def staged_recipes_pulls_files(
    staged_recipes_pr_1_files,
    staged_recipes_pr_2_files,
    staged_recipes_pr_3_files,
    staged_recipes_pr_4_files,
):
    return {
        1: staged_recipes_pr_1_files,
        2: staged_recipes_pr_2_files,
        3: staged_recipes_pr_3_files,
        4: staged_recipes_pr_4_files,
    }


@pytest.fixture
def mock_github_backend(
    app_hook_config_url,
    accessible_repos,
    app_hook_deliveries,
    app_installations,
    staged_recipes_pulls_files,
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
        "_pulls_files": {
            "pangeo-forge/staged-recipes": staged_recipes_pulls_files,
        },
    }
    return _MockGitHubBackend(**backend_kws)


def get_mock_github_session(mock_github_backend):
    def _get_mock_github_session(http_session: HttpSession):
        return MockGitHubAPI(http_session, "pangeo-forge", _backend=mock_github_backend)

    return _get_mock_github_session
