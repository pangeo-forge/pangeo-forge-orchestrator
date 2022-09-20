import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from pangeo_forge_orchestrator.http import HttpSession
from pangeo_forge_orchestrator.routers.github_app import get_jwt


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
    _app_hook_config_url: Optional[str] = None
    _accessible_repos: Optional[List[dict]] = None
    _repositories: Optional[Dict[str, dict]] = None
    _app_hook_deliveries: Optional[List[dict]] = None
    _app_installations: Optional[List[dict]] = None
    _check_runs: Optional[List[dict]] = None
    _pulls: Optional[List[dict]] = None
    _pulls_files: Optional[Dict[str, Dict[int, dict]]] = None


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
        # gidgethub allows us to call either the relative or absolute path, and we do both
        elif path.startswith("/repos/") or path.startswith("https://api.github.com/repos/"):
            if "/commits/" in path and path.endswith("/check-runs"):
                # mocks getting a check run from the github api
                commit_sha = path.split("/commits/")[-1].split("/check-runs")[0]
                check_runs = [c for c in self._backend._check_runs if c["head_sha"] == commit_sha]
                return {"total_count": len(check_runs), "check_runs": check_runs}
            elif path.endswith("branches/main"):
                # mocks getting a branch. used in create_feedstock_repo background task
                return {"commit": {"sha": "abcdefg"}}
            elif "pulls" in path and path.endswith("files"):
                # Here's an example path: "/repos/pangeo-forge/staged-recipes/pulls/1/files"
                # The next line parses this into -> "pangeo-forge/staged-recipes"
                repo_full_name = "/".join(path.split("/repos/")[-1].split("/")[0:2])
                # The next line parses this into -> `1`
                pr_number = int(path.split("/")[-2])
                return self._backend._pulls_files[repo_full_name][pr_number]
            elif "/contents/" in path:
                # mocks getting the contents for a file
                # TODO: make this more realistic. I believe the response is base64 encoded.
                # TODO: the response should vary depending on the content path here:
                relative_path_in_repo = path.split("/contents/")[-1]  # noqa: F841
                return {"content": "=B4asdfaw3fk"}
            else:
                # mocks getting a github repo id. see ``routers.github_app::get_repo_id``
                repo_full_name = path.replace("/repos/", "")
                return self._backend._repositories[repo_full_name]
        elif path == "/installation/repositories":
            return {"repositories": self._backend._accessible_repos}
        elif path.startswith("/app/hook/deliveries/"):
            id_ = int(path.replace("/app/hook/deliveries/", ""))
            return [
                {"response": d} for d in self._backend._app_hook_deliveries if d["id"] == id_
            ].pop(0)
        else:
            raise NotImplementedError(f"Path '{path}' not supported.")

    async def getiter(
        self,
        path: str,
        accept: Optional[str] = None,
        jwt: Optional[str] = None,
        oauth_token: Optional[str] = None,
    ):
        if path == "/app/hook/deliveries":
            for delivery in self._backend._app_hook_deliveries:
                yield delivery
        elif path == "/app/installations":
            for installation in self._backend._app_installations:
                yield installation
        elif path.endswith("/pulls"):
            for pr in self._backend._pulls:
                yield pr
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
            return {"token": mock_access_token_from_jwt(jwt=get_jwt())}
        elif path == "/orgs/pangeo-forge/repos":
            # mocks creating a new repo. used in `create_feedstock_repo` background task.
            # the return value is not used, so not providing one.
            pass
        elif path.endswith("/git/refs"):
            # mock creating a new git ref on a repo.
            return {
                "url": "",  # TODO: return a realistic url
                "ref": data["ref"].split("/")[-1],  # More realistic w/ or w/out `.split()`?
            }
        elif path.endswith("/pulls"):
            # mock opening a pr
            return {"number": 1}  # TODO: fixturize
        elif path.endswith("/comments"):
            return {}
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

    async def put(self, path: str, oauth_token: str, accept: str, data: Optional[dict] = None):
        # GitHub API uses the `put` method for:
        #   (1) adding content files to a branch
        #   (2) merging PRs
        if path.endswith("/merge"):
            return {"merged": True}
        else:
            # this is called for adding content files
            # TODO: actually alter state of the mock github backend here
            pass

    async def delete(self, path, oauth_token: str, accept: str, data: Optional[dict] = None):
        # used, e.g., for deleting branches (without `data` kwarg),
        # or deleting files from a branch (with `data`, for commit message, etc.)
        pass
