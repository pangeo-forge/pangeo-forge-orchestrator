import ast
import json
import os
import subprocess
from typing import Optional

from sqlmodel import Session, SQLModel
import pytest

import pangeo_forge_orchestrator.model_builders as model_builders
from pangeo_forge_orchestrator.client import Client
from pangeo_forge_orchestrator.model_builders import MultipleModels

# Exceptions ------------------------------------------------------------------------------
# The exceptions defined here provide specific Python errors to raise when certain failure
# modes are encountered which would not otherwise raise Python errors. It is useful to have
# Python errors to raise for these otherwise silent error conditions, because it allows us
# to test failure modes in a standardized manner with `pytest.raises`. Note that the errors
# we are accomodating here may *not* be silent from a human user perspective, but are rather
# silent from a programmatic perspective (i.e., they would not otherwise raise a Python error).
#
# The primary scenario we are working around here is the fact that JSON responses are returned by
# the command line interface as plain text. Therefore, unlike responses returned by the client
# interface, e.g., we cannot call `response.raise_for_status` to raise Python errors from them. The
# `_MissingFieldError`, `_StrTypeError`, `_IntTypeError`, and `_EnumTypeError` are used for this;
# i.e., they are exceptions to raise if specific error text is present in a CLI JSON response.
#
# The one other silent error covered by these exceptions is the case of a query to a the database
# that returns `None`. From the database standpoint, this is not an error per se, but we may want
# to treat it as such from the perspective of testing.


class _MissingFieldError(Exception):
    """Exception to raise if JSON returned by CLI indicates error of type `"value_error.missing"`.
    """

    pass


class _StrTypeError(Exception):
    """Exception to raise if JSON returned by CLI indicates error of type `"type_error.str"`."""

    pass


class _IntTypeError(Exception):
    """Exception to raise if JSON returned by CLI indicates error of type `"type_error.integer"`.
    """

    pass


class _EnumTypeError(Exception):
    """Exception to raise if JSON returned by CLI indicates error of type `"type_error.enum"`.
    """

    pass


class _DatetimeError(Exception):
    """Exception to raise if JSON returned by CLI indicates error of type `"value_error.datetime"`.
    """

    pass


class _NonexistentTableError(Exception):
    """Execption to raise if a database query returns `None`."""

    pass


# Helpers ---------------------------------------------------------------------------------


def commit_to_session(session: Session, model: SQLModel) -> None:
    session.add(model)
    session.commit()

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
            if error["type"] == "value_error.missing":
                raise _MissingFieldError
            elif error["type"] == "type_error.str":
                raise _StrTypeError
            elif error["type"] == "type_error.integer":
                raise _IntTypeError
            elif error["type"] == "type_error.enum":
                raise _EnumTypeError
            elif error["type"] == "value_error.datetime":
                raise _DatetimeError
    return data


class ClientCRUD:
    """Client interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    def __init__(self, base_url):
        self.base_url = base_url
        self.client = Client(base_url)

    def create(self, models: MultipleModels, json: dict) -> dict:
        response = self.client.post(models.path, json)
        response.raise_for_status()
        data = response.json()
        return data

    def read_range(self, models: MultipleModels) -> dict:
        response = self.client.get(models.path)
        assert response.status_code == 200
        data = response.json()
        return data

    def read_single(self, models: MultipleModels, table: SQLModel) -> dict:
        response = self.client.get(f"{models.path}{table.id}")
        response.raise_for_status()
        data = response.json()
        return data

    def update(
        self, models: MultipleModels, table: SQLModel, update_with: dict,
    ) -> dict:
        client = Client(base_url)
        response = client.patch(f"{models.path}{table.id}", json=update_with)
        response.raise_for_status()
        data = response.json()
        return data

    def delete(self, models: MultipleModels, table: SQLModel) -> None:
        client = Client(base_url)
        delete_response = client.delete(f"{models.path}{table.id}")
        # `assert delete_response.status_code == 200`, indicating successful deletion,
        # is commented out in favor of `raise_for_status`, for compatibility with the
        # `TestDelete.test_delete_nonexistent`
        delete_response.raise_for_status()
        get_response = client.get(f"{models.path}{table.id}")
        assert get_response.status_code == 404  # not found, b/c deleted


class CommandLineCRUD:
    """CLI interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    def __init__(self, base_url):
        self.base_url = base_url

    def create(self, models: MultipleModels, request: dict) -> dict:
        data = get_data_from_cli("post", self.base_url, models.path, request)
        return data

    def read_range(self, models: MultipleModels) -> dict:
        data = get_data_from_cli("get", self.base_url, models.path)
        return data

    def read_single(self, models: MultipleModels, table: SQLModel) -> dict:
        data = get_data_from_cli("get", self.base_url, f"{models.path}{table.id}")
        return data

    def update(
        self, models: MultipleModels, table: SQLModel, update_with: dict,
    ) -> dict:
        data = get_data_from_cli("patch", self.base_url, f"{models.path}{table.id}", update_with)
        return data

    def delete(self, models: MultipleModels, table: SQLModel) -> None:
        delete_response = get_data_from_cli("delete", self.base_url, f"{models.path}{table.id}")
        assert delete_response == {"ok": True}  # successfully deleted
        get_response = get_data_from_cli("get", self.base_url, f"{models.path}{table.id}")
        assert get_response == {"detail": f"{models.table.__name__} not found"}


@pytest.fixture(params=[ClientCRUD, CommandLineCRUD])
def client(request, http_server_url):
    CRUDClass = request.param
    return CRUDClass(http_server_url)
