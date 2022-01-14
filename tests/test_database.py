import copy
from datetime import datetime
from typing import List, Optional, Tuple

import fastapi
import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from requests.exceptions import HTTPError
from sqlmodel import Session, SQLModel

import pangeo_forge_orchestrator.abstractions as abstractions

from .conftest import APIErrors, ModelFixture, ModelFixtures, UpdateFixtures
from .interfaces import (
    AbstractionCRUD,
    ClientCRUD,
    CommandLineCRUD,
    DatabaseCRUD,
    _DatetimeError,
    _EnumTypeError,
    _IntTypeError,
    _MissingFieldError,
    _NonexistentTableError,
    _StrTypeError,
)


def add_z(input_string: str):
    if not input_string.endswith("Z"):
        input_string += "Z"
    return input_string


def parse_to_datetime(input_string: str):
    input_string = add_z(input_string)
    return datetime.strptime(input_string, "%Y-%m-%dT%H:%M:%SZ")


def registered_routes(app: FastAPI):
    return [r for r in app.routes if isinstance(r, fastapi.routing.APIRoute)]


# Test endpoint registration ------------------------------------------------------------


class TestRegistration(ModelFixtures):
    def test_registration(uncleared_session: Session, success_only_models: ModelFixture):
        models = success_only_models.models
        new_app = FastAPI()

        # assert that this application has no registered routes
        assert len(registered_routes(new_app)) == 0

        def get_session():
            yield uncleared_session

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


# Base logic ----------------------------------------------------------------------------


class BaseLogic:
    def get_connection(self, session: Session, url: str):
        """Different fixtures require different connection points to the database. `db` and
        `abstraction` interfaces use a `session` connection, whereas `client` and `cli`
        interfaces connect via the http URL. This function finds the appropriate connection
        point based on the interface.
        """
        connection = session if "db" in self.interface or "abstract" in self.interface else url
        return connection

    @staticmethod
    def commit_to_session(
        model_fixture: ModelFixture, session: Session, ntables: int = 1
    ) -> Tuple[abstractions.MultipleModels, Tuple[SQLModel, SQLModel]]:
        """

        """
        models, kws = model_fixture.models, model_fixture.success_kws
        tables = [models.table(**kw) for kw in (kws.all, kws.reqs_only)]
        for i in range(ntables):
            session.add(tables[i])
            session.commit()
        return models, tables


# Test create ---------------------------------------------------------------------------


class CreateSuccessOnly(BaseLogic, ModelFixtures):
    """Container for tests of successful database entry creation"""

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

    @pytest.mark.parametrize("fields", ["all_fields", "req_only"])
    def test_create(
        self, fields: str, success_only_models: ModelFixture, session: Session, http_server: str,
    ):
        models, kws = success_only_models.models, success_only_models.success_kws
        request = kws.all if fields == "all_fields" else kws.reqs_only
        # TODO: Explain blank_opts.
        blank_opts = None if fields == "all_fields" else list(set(kws.all) - set(kws.reqs_only))
        connection = self.get_connection(session, http_server)
        data = self.create(connection, models, request)  # `self.create` inherited from `*CRUD` obj
        self.evaluate_data(request, data, blank_opts)


class CreateComplete(CreateSuccessOnly):
    """Container for tests of both successful _and_ failing database entry creation

    Note this is used for public interfaces: client and command line.
    """

    def get_error(self, failure_mode: str):
        errors = dict(client=HTTPError)
        cli_errors = {
            APIErrors.missing: _MissingFieldError,
            APIErrors.str: _StrTypeError,
            APIErrors.enum: _EnumTypeError,
            APIErrors.int: _IntTypeError,
            APIErrors.datetime: _DatetimeError,
        }
        errors.update(dict(cli=cli_errors[failure_mode]))
        return errors[self.interface]  # `self.interface` inherited from `*CRUD` obj

    def test_create_incomplete_request(
        self, success_only_models: ModelFixture, session: Session, http_server: str,
    ):
        """Even though this is a failure test, we use success_only_models, because the failure mode
        is incomplete.

        """
        models, kws = success_only_models.models, success_only_models.success_kws
        incomplete_kwargs = copy.deepcopy(kws.reqs_only)  # NOTE: Use of `reqs_only`
        del incomplete_kwargs[next(iter(incomplete_kwargs))]  # Remove a required field

        connection = self.get_connection(session, http_server)
        error_cls = self.get_error(APIErrors.missing)
        with pytest.raises(error_cls):
            _ = self.create(connection, models, incomplete_kwargs)

    def test_create_failing_request(
        self, complete_models: ModelFixture, session: Session, http_server: str,
    ):
        models, success_kws, failure_kws = (
            complete_models.models,
            complete_models.success_kws,
            complete_models.failure_kws,
        )
        failing_request = copy.deepcopy(success_kws.all)  # NOTE: Use of `all`
        failing_request.update(failure_kws.update_with)
        error_cls = self.get_error(failure_kws.raises)

        connection = self.get_connection(session, http_server)
        error_cls = self.get_error(failure_kws.raises)
        with pytest.raises(error_cls):
            _ = self.create(connection, models, failing_request)


class TestCreateDatabase(CreateSuccessOnly, DatabaseCRUD):
    """

    Note only tested for success.
    """

    pass


class TestCreateAbstraction(CreateSuccessOnly, AbstractionCRUD):
    """

    Note only tested for success.
    """

    pass


class TestCreateClient(CreateComplete, ClientCRUD):
    """

    """

    pass


class TestCreateCommandLine(CreateComplete, CommandLineCRUD):
    """

    """

    pass


# Test read -----------------------------------------------------------------------------


class ReadLogic(BaseLogic, ModelFixtures):
    """Container for tests of reading from database"""

    def get_error(self):
        errors = dict(
            db=_NonexistentTableError,
            abstraction=HTTPException,
            client=HTTPError,
            cli=_IntTypeError,
        )
        return errors[self.interface]

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

    def test_read_range(
        self, success_only_models: ModelFixture, session: Session, http_server: str,
    ):
        models, tables = self.commit_to_session(success_only_models, session, ntables=2)
        connection = self.get_connection(session, http_server)
        data = self.read_range(connection, models)
        self.evaluate_read_range_data(data, tables)

    def test_read_single(
        self, success_only_models: ModelFixture, session: Session, http_server: str,
    ):
        models, tables = self.commit_to_session(success_only_models, session)
        connection = self.get_connection(session, http_server)
        data = self.read_single(connection, models, tables[0])
        self.evaluate_read_single_data(data, tables[0])

    def test_read_nonexistent(
        self, success_only_models: ModelFixture, session: Session, http_server: str,
    ):
        models, kws = success_only_models.models, success_only_models.success_kws
        table = models.table(**kws.all)
        # don't add any entries for this test
        connection = self.get_connection(session, http_server)
        error_cls = self.get_error()
        with pytest.raises(error_cls):
            _ = self.read_single(connection, models, table)


class TestReadDatabase(ReadLogic, DatabaseCRUD):
    pass


class TestReadAbstraction(ReadLogic, AbstractionCRUD):
    pass


class TestReadClient(ReadLogic, ClientCRUD):
    pass


class TestReadCommandLine(ReadLogic, CommandLineCRUD):
    pass


# Test update ---------------------------------------------------------------------------


class UpdateLogic(BaseLogic, UpdateFixtures):
    """Container for tests of updating existing entries in database"""

    def get_error(self):
        errors = dict(
            db=_NonexistentTableError,
            abstraction=_NonexistentTableError,
            client=HTTPError,
            cli=_IntTypeError,
        )
        return errors[self.interface]

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

    def test_update(self, session, model_to_update, http_server):
        models, table, update_with = model_to_update
        # commit_to_session(session, table)  # add entry for this test
        connection = self.get_connection(session, http_server)
        data = self.update(connection, models, table, update_with)
        self.evaluate_data(data, table, update_with)

    def test_update_nonexistent(self, session, model_to_update, http_server):
        models, table, update_with = model_to_update
        # NOTE: We *don't* add any entries for this test
        connection = self.get_connection(session, http_server)
        error_cls = self.get_error()
        with pytest.raises(error_cls):
            _ = self.update(connection, models, table, update_with)


class TestUpdateDatabase(UpdateLogic, DatabaseCRUD):
    pass


class TestUpdateAbstraction(UpdateLogic, AbstractionCRUD):
    pass


class TestUpdateClient(UpdateLogic, ClientCRUD):
    pass


class TestUpdateCommandLine(UpdateLogic, CommandLineCRUD):
    pass


# Test delete ---------------------------------------------------------------------------


class DeleteLogic(BaseLogic, ModelFixtures):
    """Container for tests of deleting existing entries in database"""

    def get_error(self):
        errors = dict(abstraction=HTTPException, client=HTTPError, cli=_IntTypeError,)
        return errors[self.interface]

    def test_delete(self, success_only_models: ModelFixture, session: Session, http_server: str):
        models, tables = self.commit_to_session(success_only_models, session)

        model_in_db = session.get(models.table, tables[0].id)
        assert model_in_db is not None
        assert model_in_db == tables[0]

        connection = self.get_connection(session, http_server)
        self.delete(connection, models, tables[0])

    def test_delete_nonexistent(
        self, success_only_models: ModelFixture, session: Session, http_server: str,
    ):
        models, kws = success_only_models.models, success_only_models.success_kws
        table = models.table(**kws.all)
        # NOTE: We *don't* add any entries for this test

        connection = self.get_connection(session, http_server)

        if self.interface == "db":
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
            error_cls = self.get_error()
            with pytest.raises(error_cls):
                _ = self.delete(connection, models, table)


class TestDeleteDatabase(DeleteLogic, DatabaseCRUD):
    pass


class TestDeleteAbstraction(DeleteLogic, AbstractionCRUD):
    pass


class TestDeleteClient(DeleteLogic, ClientCRUD):
    pass


class TestDeleteCommandLine(DeleteLogic, CommandLineCRUD):
    pass
