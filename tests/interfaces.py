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
