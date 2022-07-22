import json
from contextlib import contextmanager

import pytest
from requests.exceptions import HTTPError


@contextmanager
def passthrough(*args, **kwargs):
    yield
    return


@contextmanager
def check_error_and_skip(*args, **kwargs):
    # make sure we get an error if we try an authorized path
    with pytest.raises(HTTPError, match="403 Client Error") as e:
        yield e
    pytest.skip("Test can't proceed without auth")


def authorization_context(api_key):
    if api_key:
        return passthrough
    else:
        return check_error_and_skip


class FastAPITestClientCRUD:
    """Client interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    error_cls = HTTPError

    def __init__(self, client, api_key=None):
        self.client = client
        if api_key:
            header = {"x-api-key": api_key}
            self.client.headers.update(header)
        self.auth_required = authorization_context(api_key)

    def create(self, path: str, json: dict) -> dict:
        response = self.client.post(path, json=json)
        response.raise_for_status()
        data = response.json()
        return data

    def read_range(self, path: str) -> dict:
        response = self.client.get(path)
        return response.json()

    def read_single(self, path: str, id: int) -> dict:
        response = self.client.get(f"{path}{id}")
        response.raise_for_status()
        data = response.json()
        return data

    def update(
        self,
        path: str,
        id: int,
        update_with: dict,
    ) -> dict:
        response = self.client.patch(f"{path}{id}", json=update_with)
        response.raise_for_status()
        data = response.json()
        return data

    def delete(self, path: str, id: int) -> None:
        delete_response = self.client.delete(f"{path}{id}")
        # `assert delete_response.status_code == 200`, indicating successful deletion,
        # is commented out in favor of `raise_for_status`, for compatibility with the
        # `TestDelete.test_delete_nonexistent`
        delete_response.raise_for_status()
        return delete_response


def parse_cli_response(response):
    # useful for debugging:
    # for prop in ["stdout_bytes", "stderr_bytes", "return_value", "exit_code", "exception", "exc_info"]:  # noqa: E501
    #    print(f'response.{prop}', getattr(response, prop))
    if response.exit_code:
        raise response.exception
    if response.stdout:
        return json.loads(response.stdout_bytes)


class CLIError(Exception):
    pass


class CommandLineCRUD:
    """CLI interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    error_cls = HTTPError

    def __init__(self, app, runner):
        self.app = app
        self.runner = runner
        api_key = self.runner.env.get("PANGEO_FORGE_API_KEY", None)
        self.auth_required = authorization_context(api_key)

    def _invoke(self, *cmds: str):
        response = self.runner.invoke(self.app, ["database"] + list(cmds))
        return parse_cli_response(response)

    def create(self, path: str, request: dict) -> dict:
        return self._invoke("post", path, json.dumps(request))

    def read_range(self, path: str) -> dict:
        return self._invoke("get", path)

    def read_single(self, path: str, id: int) -> dict:
        return self._invoke("get", f"{path}{id}")

    def update(
        self,
        path: str,
        id: int,
        update_with: dict,
    ) -> dict:
        return self._invoke("patch", f"{path}{id}", json.dumps(update_with))

    def delete(self, path: str, id: int) -> None:
        return self._invoke("delete", f"{path}{id}")
