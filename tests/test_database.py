import copy
from datetime import datetime
from typing import Callable, List, Optional

import fastapi
import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from pydantic import ValidationError
from requests.exceptions import HTTPError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

import pangeo_forge_orchestrator.abstractions as abstractions

from .conftest import CreateFixtures, DeleteFixtures, ModelFixture, ReadFixtures, UpdateFixtures
from .interfaces import (
    _IntTypeError,
    _MissingFieldError,
    _NonexistentTableError,
    _StrTypeError,
    clear_table,
)


def commit_to_session(session: Session, model: SQLModel):
    session.add(model)
    session.commit()


def add_z(input_string: str):
    if not input_string.endswith("Z"):
        input_string += "Z"
    return input_string


def parse_to_datetime(input_string: str):
    input_string = add_z(input_string)
    return datetime.strptime(input_string, "%Y-%m-%dT%H:%M:%SZ")


def registered_routes(app: FastAPI):
    return [r for r in app.routes if isinstance(r, fastapi.routing.APIRoute)]


def get_interface(func: Callable):
    # This function returns the interface name from its associated callable
    # (i.e. it returns "db" from "create_with_db", etc.)
    return func.__name__.split("_with_")[1]


def get_connection(session: Session, url: str, func: Callable):
    # Different fixtures require different connection points to the database.
    # `db` and `abstraction` interfaces use a `session` connection, whereas
    # `client` and `cli` interfaces connect via the http URL. This function
    # finds the appropriate connection point based on the interface.
    interface = get_interface(func)
    connection = session if "db" in interface or "abstract" in interface else url
    return connection


# Test endpoint registration ------------------------------------------------------------


def test_registration(session, models_with_kwargs):
    models = models_with_kwargs.models
    new_app = FastAPI()

    # assert that this application has no registered routes
    assert len(registered_routes(new_app)) == 0

    def get_session():
        yield session

    # register routes for this application
    abstractions.register_endpoints(api=new_app, get_session=get_session, models=models)

    # assert that this application now has five registered routes
    routes = registered_routes(new_app)

    assert len(routes) == 5

    expected_names = ("_create", "_read_range", "_read_single", "_update", "_delete")
    # Check names
    for r in routes:
        assert r.name in expected_names
    # Check routes
    for r in routes:
        if r.name in ("_create", "_read_range"):
            assert r.path == models.path
        elif r.name in ("_read_single", "_update", "_delete"):
            assert r.path == f"{models.path}{{id}}"
    # Check response models
    for r in routes:
        if r.name in ("_create", "_read_single", "_update"):
            assert r.response_model == models.response
        elif r.name == "_read_range":
            assert r.response_model == List[models.response]
        elif r.name == "_delete":
            assert r.response_model is None


# Test create ---------------------------------------------------------------------------


class TestCreate(CreateFixtures):
    """Container for tests of database entry creation and associated failure modes"""

    @staticmethod
    def get_error(func: Callable, failure_mode: str):
        interface = get_interface(func)
        errors = dict(db=IntegrityError, abstraction=ValidationError, client=HTTPError,)
        cli_error = _MissingFieldError if failure_mode == "incomplete" else _StrTypeError
        errors.update(dict(cli=cli_error))
        return errors[interface]

    @staticmethod
    def evaluate_data(request: dict, data: dict, blank_opts: Optional[List] = None):
        for k in request.keys():
            if isinstance(data[k], datetime):
                assert data[k] == parse_to_datetime(request[k])
            elif (
                # Pydantic requires a "Z"-terminated timestamp, but FastAPI responds without the "Z"
                isinstance(data[k], str)
                and isinstance(request[k], str)
                and any([s.endswith("Z") for s in (data[k], request[k])])
                and not all([s.endswith("Z") for s in (data[k], request[k])])
            ):
                assert add_z(data[k]) == add_z(request[k])
            else:
                assert data[k] == request[k]
        if blank_opts:
            for k in blank_opts:
                assert data[k] is None
        assert data["id"] is not None

    def test_create(
        self,
        session: Session,
        model_to_create: ModelFixture,
        http_server: str,
        create_func: Callable,
    ):
        models, request, blank_opts = model_to_create
        clear_table(session, models.table)  # make sure the database is empty
        connection = get_connection(session, http_server, create_func)
        data = create_func(connection, models, request)
        self.evaluate_data(request, data, blank_opts)

    @pytest.mark.parametrize("failure_mode", ["incomplete", "invalid"])
    def test_create_failure(
        self,
        session: Session,
        model_to_create: ModelFixture,
        http_server: str,
        create_func: Callable,
        failure_mode: str,
    ):
        models, request, _ = model_to_create
        clear_table(session, models.table)  # make sure the database is empty
        connection = get_connection(session, http_server, create_func)

        failing_request = copy.deepcopy(request)
        if failure_mode == "incomplete":
            del failing_request[list(failing_request)[0]]  # Remove a required field
        else:
            assert type(request[list(request)[0]]) == str
            failing_request[list(failing_request)[0]] = {"message": "Is this wrong?"}
            assert type(failing_request[list(failing_request)[0]]) == dict

        error_cls = self.get_error(create_func, failure_mode=failure_mode)
        with pytest.raises(error_cls):
            _ = create_func(connection, models, failing_request)


# Test read -----------------------------------------------------------------------------


class TestRead(ReadFixtures):
    """Container for tests of reading from database"""

    @staticmethod
    def get_error(func: Callable):
        interface = get_interface(func)
        errors = dict(
            db=_NonexistentTableError,
            abstraction=HTTPException,
            client=HTTPError,
            cli=_IntTypeError,
        )
        return errors[interface]

    @staticmethod
    def evaluate_read_range_data(data, tables):
        assert len(data) == len(tables)
        for i, t in enumerate(tables):
            input_data = t.dict()
            # `session.query` returns a list of `SQLModel` table instances
            # ... but `client.get` returns a list of `dict`s, so:
            response_data = data[i].dict() if type(data[i]) != dict else data[i]
            for k in input_data.keys():
                if type(input_data[k]) == datetime and type(response_data[k]) != datetime:
                    assert parse_to_datetime(response_data[k]) == input_data[k]
                else:
                    assert response_data[k] == input_data[k]

    @staticmethod
    def evaluate_read_single_data(data, table):
        input_dict = table.dict()
        for k in input_dict.keys():
            if type(input_dict[k]) == datetime and type(data[k]) != datetime:
                assert parse_to_datetime(data[k]) == input_dict[k]
            else:
                assert data[k] == input_dict[k]

    def test_read_range(self, session, models_to_read, http_server, read_range_func):
        models, tables = models_to_read
        clear_table(session, models.table)  # make sure the database is empty
        for t in tables:
            commit_to_session(session, t)  # add entries for this test
        connection = get_connection(session, http_server, read_range_func)
        data = read_range_func(connection, models)
        self.evaluate_read_range_data(data, tables)

    def test_read_single(self, session, single_model_to_read, http_server, read_single_func):
        models, table = single_model_to_read
        clear_table(session, models.table)  # make sure the database is empty
        commit_to_session(session, table)  # add entries for this test
        connection = get_connection(session, http_server, read_single_func)
        data = read_single_func(connection, models, table)
        self.evaluate_read_single_data(data, table)

    def test_read_nonexistent(self, session, single_model_to_read, http_server, read_single_func):
        models, table = single_model_to_read
        clear_table(session, models.table)  # make sure the database is empty
        # don't add any entries for this test
        connection = get_connection(session, http_server, read_single_func)
        error_cls = self.get_error(read_single_func)
        with pytest.raises(error_cls):
            _ = read_single_func(connection, models, table)


# Test update ---------------------------------------------------------------------------


class TestUpdate(UpdateFixtures):
    """Container for tests of updating existing entries in database"""

    @staticmethod
    def get_error(func: Callable):
        interface = get_interface(func)
        errors = dict(
            db=_NonexistentTableError,
            abstraction=_NonexistentTableError,
            client=HTTPError,
            cli=_IntTypeError,
        )
        return errors[interface]

    @staticmethod
    def evaluate_data(data, table, update_with):
        assert data["id"] == table.id
        input_dict = table.dict()
        for k in input_dict.keys():
            if k == list(update_with)[0]:
                assert data[k] == update_with[k]
            else:
                if not isinstance(data[k], type(input_dict[k])):
                    assert parse_to_datetime(data[k]) == input_dict[k]
                else:
                    assert data[k] == input_dict[k]

    def test_update(self, session, model_to_update, http_server, update_func):
        models, table, update_with = model_to_update
        clear_table(session, models.table)  # make sure the database is empty
        commit_to_session(session, table)  # add entry for this test
        connection = get_connection(session, http_server, update_func)
        data = update_func(connection, models, table, update_with)
        self.evaluate_data(data, table, update_with)

    def test_update_nonexistent(self, session, model_to_update, http_server, update_func):
        models, table, update_with = model_to_update
        clear_table(session, models.table)  # make sure the database is empty
        # don't add any entries for this test
        connection = get_connection(session, http_server, update_func)
        error_cls = self.get_error(update_func)
        with pytest.raises(error_cls):
            _ = update_func(connection, models, table, update_with)


# Test delete ---------------------------------------------------------------------------


class TestDelete(DeleteFixtures):
    """Container for tests of deleting existing entries in database"""

    @staticmethod
    def get_error(func: Callable):
        interface = get_interface(func)
        errors = dict(abstraction=HTTPException, client=HTTPError, cli=_IntTypeError,)
        return errors[interface]

    def test_delete(self, session, model_to_delete, http_server, delete_func):
        models, table = model_to_delete
        clear_table(session, models.table)  # make sure the database is empty
        commit_to_session(session, table)  # add entries for this test

        model_in_db = session.get(models.table, table.id)
        assert model_in_db is not None
        assert model_in_db == table

        connection = get_connection(session, http_server, delete_func)
        delete_func(connection, models, table)

    def test_delete_nonexistent(self, session, model_to_delete, http_server, delete_func):
        models, table = model_to_delete
        clear_table(session, models.table)  # make sure the database is empty
        connection = get_connection(session, http_server, delete_func)

        if get_interface(delete_func) == "db":
            pytest.skip(
                "Deleting via the database is a `session.query` followed by `.delete()`. So far, "
                "these tests do not implement id-level queries with the session API (only queries "
                "for all items). This is not generally a problem, as most of our interface will be "
                "via the client or the cli. In the future, we may choose to use id-level queries "
                "in the tests (or to use a different SQL API for direct DELETE without querying "
                "first). Until then, there is not an urgency to run this test for the database "
                "interface, so it is omitted here."
            )
        else:
            error_cls = self.get_error(delete_func)
            with pytest.raises(error_cls):
                _ = delete_func(connection, models, table)
