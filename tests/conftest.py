import ast
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pytest
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel, create_engine

import pangeo_forge_orchestrator.abstractions as abstractions
from pangeo_forge_orchestrator.abstractions import MultipleModels
from pangeo_forge_orchestrator.client import Client
from pangeo_forge_orchestrator.models import MODELS

# Exceptions ------------------------------------------------------------------------------


class _MissingFieldError(Exception):
    pass


class _StrTypeError(Exception):
    pass


class _IntTypeError(Exception):
    pass


class _NonexistentTableError(Exception):
    pass


# Helpers ---------------------------------------------------------------------------------


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


def start_http_server(path, request):
    port = get_open_port()
    command_list = [
        "uvicorn",
        "pangeo_forge_orchestrator.api:api",
        f"--port={port}",
        "--log-level=critical",
    ]
    p = subprocess.Popen(command_list, cwd=path)
    url = f"http://127.0.0.1:{port}"
    time.sleep(1)  # let the server start up

    def teardown():
        p.kill()

    request.addfinalizer(teardown)

    return url


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


# General fixtures ------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tempdir(tmp_path_factory):
    return tmp_path_factory.mktemp("test-database")


@pytest.fixture(scope="session")
def http_server(tempdir, request):
    url = start_http_server(tempdir, request=request)
    return url


@pytest.fixture
def session(tempdir):
    # Cf. `pangeo_forge_orchestrator.database` & `pangeo_forge_orchestrator.api`
    # Here we are creating a session for the database file which exists in the tempdir.
    # We can't reuse the `pangeo_forge_orchestrator.api:get_session` function here because
    # the session returned by that function resolves the database path via `os.getcwd()`, but
    # our tests are run from a different workind directory than the one where the database resides.
    sqlite_file_path = f"sqlite:////{tempdir}/database.db"
    connect_args = {"check_same_thread": False}
    engine = create_engine(sqlite_file_path, echo=True, connect_args=connect_args)
    with Session(engine) as session:
        yield session


# Models --------------------------------------------------------------------------------


@dataclass
class ModelKwargs:
    """Container to hold kwargs for instantiating ``SQLModel`` table model.

    :param request: The kwargs for instantatiting a table model. Can be passed to a model object
    in the Python context, or sent as JSON to the database API.
    :param blank_opts: List of any optional model fields which are excluded from the ``request``.
    """

    request: dict
    blank_opts: List[str] = field(default_factory=list)


@dataclass
class ModelFixture:
    """Container for a ``MultipleModels`` object (itself containing ``SQLModel`` objects) with
    kwargs which can be used to instiate the models within it.

    :param models: A ``MultipleModels`` object.
    :param kwargs: A list of three ``ModelKwargs`` objects matched to the ``models``.
    """

    models: MultipleModels
    kwargs: List[ModelKwargs]

    def __post_init__(self):
        if len(self.kwargs) != 3:
            raise ValueError("``len(self.kwargs)`` must equal 3.")


# To test additional models:
#   1. Add a session-scoped fixture here which returns a `ModelFixture`, the name of which should
#      be `model_key_with_kwargs`, where `model_key` is the name of the key mapping for the
#      associated `MultipleModels` object in the `pangeo_forge_orchestrator.models::MODELS` dict.
#   2. Add `lazy_fixture("model_key_with_kwargs")` to the param list of the `models_with_kwargs`
#      fixture. (Where `"model_key_with_kwargs"` is the name of the fixture you created un steo 1.)


@pytest.fixture(scope="session")
def recipe_run_with_kwargs():
    kws = [
        ModelKwargs(
            request=dict(
                recipe_id="test-recipe-0",
                run_date="2021-01-01T00:00:00Z",
                bakery_id=0,
                feedstock_id=0,
                commit="012345abcdefg",
                version="1.0",
                status="complete",
                path="/path-to-dataset.zarr",
            ),
            blank_opts=["message"],
        ),
        ModelKwargs(
            request=dict(
                recipe_id="test-recipe-1",
                run_date="2021-02-02T00:00:00Z",
                bakery_id=1,
                feedstock_id=1,
                commit="012345abcdefg",
                version="2.0",
                status="complete",
                path="/path-to-dataset.zarr",
                message="hello",
            ),
        ),
        ModelKwargs(
            request=dict(
                recipe_id="test-recipe-2",
                run_date="2021-03-03T00:00:00Z",
                bakery_id=2,
                feedstock_id=2,
                commit="012345abcdefg",
                version="3.0",
                status="complete",
                path="/path-to-dataset.zarr",
            ),
            blank_opts=["message"],
        ),
    ]
    return ModelFixture(MODELS["recipe_run"], kws)


@pytest.fixture(
    scope="session", params=[lazy_fixture("recipe_run_with_kwargs")],
)
def models_with_kwargs(request):
    return request.param


# CRUD function fixtures ------------------------------------------------------------------

# Create ----------------------------------------------------------------------------------


class CreateFixtures:
    """Fixtures for ``TestCreate``"""

    @pytest.fixture
    def create_with_db(self) -> Callable:
        def _create_with_db(session: Session, models: MultipleModels, request: dict) -> dict:
            table = models.table(**request)
            commit_to_session(session, table)
            # Need to `get` b/c db doesn't return a response
            model_db = session.get(models.table, table.id)
            data = model_db.dict()
            return data

        return _create_with_db

    @pytest.fixture
    def create_with_abstraction(self) -> Callable:
        def _create_with_abstraction(
            session: Session, models: MultipleModels, request: dict
        ) -> dict:
            table = models.table(**request)
            model_db = abstractions.create(session=session, table_cls=models.table, model=table,)
            data = model_db.dict()
            return data

        return _create_with_abstraction

    @pytest.fixture
    def create_with_client(self) -> Callable:
        def _create_with_client(base_url: str, models: MultipleModels, json: dict) -> dict:
            client = Client(base_url)
            response = client.post(models.path, json)
            response.raise_for_status()
            data = response.json()
            return data

        return _create_with_client

    @pytest.fixture
    def create_with_cli(self) -> Callable:
        def _create_with_cli(base_url: str, models: MultipleModels, request: dict) -> dict:
            data = get_data_from_cli("post", base_url, models.path, request)
            return data

        return _create_with_cli

    @pytest.fixture(
        params=[
            lazy_fixture("create_with_db"),
            lazy_fixture("create_with_abstraction"),
            lazy_fixture("create_with_client"),
            lazy_fixture("create_with_cli"),
        ],
    )
    def create_func(self, request):
        return request.param


# Read ------------------------------------------------------------------------------------


class ReadFixtures:
    """Fixtures for ``TestRead``"""

    @pytest.fixture
    def read_range_with_db(self) -> Callable:
        def _read_range_with_db(session: Session, models: MultipleModels) -> dict:
            data = session.query(models.table).all()
            return data

        return _read_range_with_db

    @pytest.fixture
    def read_range_with_abstraction(self) -> Callable:
        def _read_range_with_abstraction(session: Session, models: MultipleModels) -> dict:
            data = abstractions.read_range(
                session=session,
                table_cls=models.table,
                offset=0,
                limit=abstractions.QUERY_LIMIT.default,
            )
            return data

        return _read_range_with_abstraction

    @pytest.fixture
    def read_range_with_client(self) -> Callable:
        def _read_range_with_client(base_url: str, models: MultipleModels) -> dict:
            client = Client(base_url)
            response = client.get(models.path)
            assert response.status_code == 200
            data = response.json()
            return data

        return _read_range_with_client

    @pytest.fixture
    def read_range_with_cli(self) -> Callable:
        def _read_range_with_cli(base_url: str, models: MultipleModels) -> dict:
            data = get_data_from_cli("get", base_url, models.path)
            return data

        return _read_range_with_cli

    @pytest.fixture(
        params=[
            lazy_fixture("read_range_with_db"),
            lazy_fixture("read_range_with_abstraction"),
            lazy_fixture("read_range_with_client"),
            lazy_fixture("read_range_with_cli"),
        ],
    )
    def read_range_func(self, request):
        return request.param

    @pytest.fixture
    def read_single_with_db(self) -> Callable:
        def _read_single_with_db(session: Session, models: MultipleModels, table: SQLModel) -> dict:
            model_db = session.get(models.table, table.id)
            if model_db is None:
                raise _NonexistentTableError
            data = model_db.dict()
            return data

        return _read_single_with_db

    @pytest.fixture
    def read_single_with_abstraction(self) -> Callable:
        def _read_single_with_abstraction(
            session: Session, models: MultipleModels, table: SQLModel
        ) -> dict:
            model_db = abstractions.read_single(
                session=session, table_cls=models.table, id=table.id
            )
            data = model_db.dict()
            return data

        return _read_single_with_abstraction

    @pytest.fixture
    def read_single_with_client(self) -> Callable:
        def _read_single_with_client(
            base_url: str, models: MultipleModels, table: SQLModel
        ) -> dict:
            client = Client(base_url)
            response = client.get(f"{models.path}{table.id}")
            response.raise_for_status()
            data = response.json()
            return data

        return _read_single_with_client

    @pytest.fixture
    def read_single_with_cli(self) -> Callable:
        def _read_single_with_cli(base_url: str, models: MultipleModels, table: SQLModel) -> dict:
            data = get_data_from_cli("get", base_url, f"{models.path}{table.id}")
            return data

        return _read_single_with_cli

    @pytest.fixture(
        params=[
            lazy_fixture("read_single_with_db"),
            lazy_fixture("read_single_with_abstraction"),
            lazy_fixture("read_single_with_client"),
            lazy_fixture("read_single_with_cli"),
        ],
    )
    def read_single_func(self, request):
        return request.param


# Update --------------------------------------------------------------------------------


class UpdateFixtures:
    """Fixtures for ``TestUpdate``"""

    @pytest.fixture
    def update_with_db(self) -> Callable:
        def _update_with_db(
            session: Session, models: MultipleModels, table: SQLModel, update_with: dict,
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

        return _update_with_db

    @pytest.fixture
    def update_with_abstraction(self) -> Callable:
        def _update_with_abstraction(
            session: Session, models: MultipleModels, table: SQLModel, update_with: dict,
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

        return _update_with_abstraction

    @pytest.fixture
    def update_with_client(self) -> Callable:
        def _update_with_client(
            base_url: str, models: MultipleModels, table: SQLModel, update_with: dict,
        ) -> dict:
            client = Client(base_url)
            response = client.patch(f"{models.path}{table.id}", json=update_with)
            response.raise_for_status()
            data = response.json()
            return data

        return _update_with_client

    @pytest.fixture
    def update_with_cli(self) -> Callable:
        def _update_with_cli(
            base_url: str, models: MultipleModels, table: SQLModel, update_with: dict,
        ) -> dict:
            data = get_data_from_cli("patch", base_url, f"{models.path}{table.id}", update_with)
            return data

        return _update_with_cli

    @pytest.fixture(
        params=[
            lazy_fixture("update_with_db"),
            lazy_fixture("update_with_abstraction"),
            lazy_fixture("update_with_client"),
            lazy_fixture("update_with_cli"),
        ],
    )
    def update_func(self, request):
        return request.param


# Delete --------------------------------------------------------------------------------


class DeleteFixtures:
    """Fixtures for ``TestDelete``"""

    @pytest.fixture
    def delete_with_db(self) -> Callable:
        def _delete_with_db(session: Session, models: MultipleModels, table: SQLModel) -> None:
            # TODO: Database deletions based on specific table id (vs. below clear all).
            # Not urgent because we'll generally be doing this via either the client or cli.
            clear_table(session, models.table)
            model_in_db = session.get(models.table, table.id)
            assert model_in_db is None

        return _delete_with_db

    @pytest.fixture
    def delete_with_abstraction(self) -> Callable:
        def _delete_with_abstraction(
            session: Session, models: MultipleModels, table: SQLModel
        ) -> None:
            delete_response = abstractions.delete(
                session=session, table_cls=models.table, id=table.id
            )
            assert delete_response == {"ok": True}  # successfully deleted
            model_in_db = session.get(models.table, table.id)
            assert model_in_db is None

        return _delete_with_abstraction

    @pytest.fixture
    def delete_with_client(self) -> Callable:
        def _delete_with_client(base_url: str, models: MultipleModels, table: SQLModel) -> None:
            client = Client(base_url)
            delete_response = client.delete(f"{models.path}{table.id}")
            # `assert delete_response.status_code == 200`, indicating successful deletion,
            # is commented out in favor of `raise_for_status`, for compatibility with the
            # `TestDelete.test_delete_nonexistent`
            delete_response.raise_for_status()
            get_response = client.get(f"{models.path}{table.id}")
            assert get_response.status_code == 404  # not found, b/c deleted

        return _delete_with_client

    @pytest.fixture
    def delete_with_cli(self) -> Callable:
        def _delete_with_cli(base_url: str, models: MultipleModels, table: SQLModel) -> None:
            delete_response = get_data_from_cli("delete", base_url, f"{models.path}{table.id}")
            assert delete_response == {"ok": True}  # successfully deleted
            get_response = get_data_from_cli("get", base_url, f"{models.path}{table.id}")
            assert get_response == {"detail": f"{models.table.__name__} not found"}

        return _delete_with_cli

    @pytest.fixture(
        params=[
            lazy_fixture("delete_with_db"),
            lazy_fixture("delete_with_abstraction"),
            lazy_fixture("delete_with_client"),
            lazy_fixture("delete_with_cli"),
        ],
    )
    def delete_func(self, request):
        return request.param
