import ast
import json
import os
import subprocess
from typing import Optional

from requests.exceptions import HTTPError

from pangeo_forge_orchestrator.client import Client


class HTTPClientCRUD:
    """Client interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    error_cls = HTTPError

    def __init__(self, base_url):
        self.base_url = base_url
        self.client = Client(base_url)

    def create(self, path: str, json: dict) -> dict:
        response = self.client.post(path, json)
        response.raise_for_status()
        data = response.json()
        return data

    def read_range(self, path: str) -> dict:
        response = self.client.get(path)
        assert response.status_code == 200
        data = response.json()
        return data

    def read_single(self, path: str, id: int) -> dict:
        response = self.client.get(f"{path}{id}")
        response.raise_for_status()
        data = response.json()
        return data

    def update(self, path: str, id: int, update_with: dict,) -> dict:
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
        get_response = self.client.get(f"{path}{id}")
        assert get_response.status_code == 404  # not found, b/c deleted


def get_data_from_cli(
    request_type: str, database_url: str, endpoint: str, request: Optional[dict] = None,
) -> dict:
    os.environ["PANGEO_FORGE_DATABASE_URL"] = database_url
    cmd = ["pangeo-forge", "database", request_type, endpoint]
    if request is not None:
        cmd.append(json.dumps(request))
    stdout = subprocess.check_output(cmd)
    data = ast.literal_eval(stdout.decode("utf-8"))
    if isinstance(data, dict) and "detail" in data.keys():
        error = data["detail"][0]
        if isinstance(error, dict):
            raise CLIError(error["type"])
        else:
            assert False, "This should probably never happen?"
    return data


class CLIError(Exception):
    pass


class CommandLineCRUD:
    """CLI interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    error_cls = CLIError

    def __init__(self, base_url):
        self.base_url = base_url

    def create(self, path: str, request: dict) -> dict:
        data = get_data_from_cli("post", self.base_url, path, request)
        return data

    def read_range(self, path: str) -> dict:
        data = get_data_from_cli("get", self.base_url, path)
        return data

    def read_single(self, path: str, id: int) -> dict:
        data = get_data_from_cli("get", self.base_url, f"{path}{id}")
        return data

    def update(self, path: str, id: int, update_with: dict,) -> dict:
        data = get_data_from_cli("patch", self.base_url, f"{path}{id}", update_with)
        return data

    def delete(self, path: str, id: int) -> None:
        delete_response = get_data_from_cli("delete", self.base_url, f"{path}{id}")
        assert delete_response == {"ok": True}  # successfully deleted
        get_response = get_data_from_cli("get", self.base_url, f"{path}{id}")
        assert get_response == {"detail": "not found"}
