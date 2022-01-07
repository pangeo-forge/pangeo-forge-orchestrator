import ast
import json
import os
import subprocess
from typing import Optional

from sqlmodel import Session, SQLModel

import pangeo_forge_orchestrator.abstractions as abstractions
from pangeo_forge_orchestrator.abstractions import MultipleModels
from pangeo_forge_orchestrator.client import Client

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
# `_MissingFieldError`, `_StrTypeError`, and `_IntTypeError` are all for use in this context;
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


class _NonexistentTableError(Exception):
    """Execption to raise if a database query returns `None`."""

    pass


# Helpers ---------------------------------------------------------------------------------


def commit_to_session(session: Session, model: SQLModel) -> None:
    session.add(model)
    session.commit()


def clear_table(session: Session, table_model: SQLModel):
    session.query(table_model).delete()
    session.commit()
    assert len(session.query(table_model).all()) == 0  # make sure the database is empty


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
    return data


# Containers ------------------------------------------------------------------------------


class DatabaseCRUD:
    """Database interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    interface = "db"

    def create(self, session: Session, models: MultipleModels, request: dict) -> dict:
        table = models.table(**request)
        commit_to_session(session, table)
        # Need to `get` b/c db doesn't return a response
        model_db = session.get(models.table, table.id)
        data = model_db.dict()
        return data

    def read_range(self, session: Session, models: MultipleModels) -> dict:
        data = session.query(models.table).all()
        return data

    def read_single(self, session: Session, models: MultipleModels, table: SQLModel) -> dict:
        model_db = session.get(models.table, table.id)
        if model_db is None:
            raise _NonexistentTableError
        data = model_db.dict()
        return data

    def update(
        self, session: Session, models: MultipleModels, table: SQLModel, update_with: dict,
    ) -> dict:
        model_db = session.query(models.table).first()
        if model_db is None:
            raise _NonexistentTableError
        for k, v in update_with.items():
            setattr(model_db, k, v)
        session.commit()
        model_db = session.get(models.table, table.id)
        data = model_db.dict()
        return data

    def delete(self, session: Session, models: MultipleModels, table: SQLModel) -> None:
        # TODO: Database deletions based on specific table id (vs. below clear all).
        # Not urgent because we'll generally be doing this via either the client or cli.
        clear_table(session, models.table)
        model_in_db = session.get(models.table, table.id)
        assert model_in_db is None


class AbstractionCRUD:
    """Abstraction interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    interface = "abstraction"

    def create(self, session: Session, models: MultipleModels, request: dict) -> dict:
        table = models.table(**request)
        model_db = abstractions.create(session=session, table_cls=models.table, model=table,)
        data = model_db.dict()
        return data

    def read_range(self, session: Session, models: MultipleModels) -> dict:
        data = abstractions.read_range(
            session=session,
            table_cls=models.table,
            offset=0,
            limit=abstractions.QUERY_LIMIT.default,
        )
        return data

    def read_single(self, session: Session, models: MultipleModels, table: SQLModel) -> dict:
        model_db = abstractions.read_single(session=session, table_cls=models.table, id=table.id)
        data = model_db.dict()
        return data

    def update(
        self, session: Session, models: MultipleModels, table: SQLModel, update_with: dict,
    ) -> dict:
        model_db = session.query(models.table).first()
        if model_db is None:
            raise _NonexistentTableError
        for k, v in update_with.items():
            setattr(model_db, k, v)
        updated_model = abstractions.update(
            session=session, table_cls=models.table, id=model_db.id, model=model_db
        )
        data = updated_model.dict()
        return data

    def delete(self, session: Session, models: MultipleModels, table: SQLModel) -> None:
        delete_response = abstractions.delete(session=session, table_cls=models.table, id=table.id)
        assert delete_response == {"ok": True}  # successfully deleted
        model_in_db = session.get(models.table, table.id)
        assert model_in_db is None


class ClientCRUD:
    """Client interface CRUD functions to pass to the fixtures objects in ``conftest.py``"""

    interface = "client"

    def create(self, base_url: str, models: MultipleModels, json: dict) -> dict:
        client = Client(base_url)
        response = client.post(models.path, json)
        response.raise_for_status()
        data = response.json()
        return data

    def read_range(self, base_url: str, models: MultipleModels) -> dict:
        client = Client(base_url)
        response = client.get(models.path)
        assert response.status_code == 200
        data = response.json()
        return data

    def read_single(self, base_url: str, models: MultipleModels, table: SQLModel) -> dict:
        client = Client(base_url)
        response = client.get(f"{models.path}{table.id}")
        response.raise_for_status()
        data = response.json()
        return data

    def update(
        self, base_url: str, models: MultipleModels, table: SQLModel, update_with: dict,
    ) -> dict:
        client = Client(base_url)
        response = client.patch(f"{models.path}{table.id}", json=update_with)
        response.raise_for_status()
        data = response.json()
        return data

    def delete(self, base_url: str, models: MultipleModels, table: SQLModel) -> None:
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

    interface = "cli"

    def create(self, base_url: str, models: MultipleModels, request: dict) -> dict:
        data = get_data_from_cli("post", base_url, models.path, request)
        return data

    def read_range(self, base_url: str, models: MultipleModels) -> dict:
        data = get_data_from_cli("get", base_url, models.path)
        return data

    def read_single(self, base_url: str, models: MultipleModels, table: SQLModel) -> dict:
        data = get_data_from_cli("get", base_url, f"{models.path}{table.id}")
        return data

    def update(
        self, base_url: str, models: MultipleModels, table: SQLModel, update_with: dict,
    ) -> dict:
        data = get_data_from_cli("patch", base_url, f"{models.path}{table.id}", update_with)
        return data

    def delete(self, base_url: str, models: MultipleModels, table: SQLModel) -> None:
        delete_response = get_data_from_cli("delete", base_url, f"{models.path}{table.id}")
        assert delete_response == {"ok": True}  # successfully deleted
        get_response = get_data_from_cli("get", base_url, f"{models.path}{table.id}")
        assert get_response == {"detail": f"{models.table.__name__} not found"}
