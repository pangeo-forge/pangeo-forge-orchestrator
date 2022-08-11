import hashlib
import os
import uuid

import pytest
import pytest_asyncio
import yaml
from asgi_lifespan import LifespanManager
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pytest_lazyfixture import lazy_fixture
from sqlmodel import Session, SQLModel

import pangeo_forge_orchestrator
from pangeo_forge_orchestrator.api import app
from pangeo_forge_orchestrator.database import maybe_create_db_and_tables
from pangeo_forge_orchestrator.models import MODELS

from .interfaces import FastAPITestClientCRUD

    private_key, _ = rsa_key_pair
    return private_key

@pytest.fixture(autouse=True, scope="session")
def setup_and_teardown():
    if os.environ["DATABASE_URL"].startswith("sqlite") and os.path.exists("./database.sqlite"):
        # Assumes tests are invoked from repo root (not within tests/ directory).
        raise ValueError(
            "Preexisting `./database.sqlite` may cause test failures. Please remove this file "
            "then restart test session."
        )
    # TODO: remove this call to `maybe_create_db_and_tables`. This function is called on app
    # start-up, so we really shouldn't need to call it manually. However, given how we are handling
    # keeping the tables empty via the ``session`` fixture below, if we do not call this function
    # here, there will not be a ``database.sqlite`` file available when ``session`` is collected.
    # A forthcoming refactor of the test fixtures can resolve this, but for now it's okay to have
    # this called twice (once now and once at app start-up), because it should be idempotent.
    maybe_create_db_and_tables()
    yield
    # teardown here (none for now)


def clear_table(session: Session, table_model: SQLModel):
    session.query(table_model).delete()
    if session.connection().engine.url.drivername == "postgresql":
        # if testing against persistent local postgres server, reset primary keys
        cmd = f"ALTER SEQUENCE {table_model.__name__}_id_seq RESTART WITH 1"
        session.exec(cmd)
    session.commit()
    assert len(session.query(table_model).all()) == 0  # make sure the database is empty


@pytest.fixture(scope="session")
def api_keys():
    salt = uuid.uuid4().hex
    raw_key = uuid.uuid4().hex
    encrypted_key = hashlib.sha256(salt.encode() + raw_key.encode()).hexdigest()
    return salt, raw_key, encrypted_key


@pytest.fixture(scope="session")
def admin_key(api_keys):
    _, raw_key, _ = api_keys
    return raw_key


@pytest.fixture
def session():
    from pangeo_forge_orchestrator.database import engine

    with Session(engine) as session:
        for k in MODELS:
            clear_table(session, MODELS[k].table)  # make sure the database is empty
        yield session


# the next two fixtures use the session fixture to clear the database


@pytest.fixture
def fastapi_test_crud_client(session):
    with TestClient(app) as fastapi_test_client:
        yield FastAPITestClientCRUD(fastapi_test_client)


@pytest.fixture
def fastapi_test_crud_client_authorized(session, admin_key):
    with TestClient(app) as fastapi_test_client:
        return FastAPITestClientCRUD(fastapi_test_client, api_key=admin_key)


# alias
authorized_client = fastapi_test_crud_client_authorized


@pytest.fixture(
    params=[
        lazy_fixture("fastapi_test_crud_client"),
        lazy_fixture("fastapi_test_crud_client_authorized"),
    ]
)
def client(request):
    return request.param
