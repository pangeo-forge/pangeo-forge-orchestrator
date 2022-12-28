import os

from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine  # noqa: F401


def get_database_url_from_env():
    try:
        database_url = os.environ["DATABASE_URL"]
    except KeyError as e:  # pragma: no cover
        raise ValueError(
            "Application can't run unless DATABASE_URL environment variable is set"
        ) from e

    if database_url.startswith("postgres://"):  # pragma: no cover
        # Fix Heroku's incompatible postgres database uri
        # https://stackoverflow.com/a/67754795/3266235
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return database_url


connect_args = {}  # type: dict
database_url = get_database_url_from_env()
if database_url.startswith("sqlite:"):
    connect_args = {"check_same_thread": False}
if database_url.startswith("postgresql:"):
    connect_args = dict(options="-c timezone=utc")


# Temporarily using the NullPool here to workaround error being raised in tests:
# `sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out`
# ...for which I am not able to find the "real" solution for. NullPool comes with a performance
# cost, but at the moment we are dealing with sufficiently small request volume that it shouldn't be
# noticable in production.
engine = create_engine(database_url, echo=False, connect_args=connect_args, poolclass=NullPool)


def get_session():
    with Session(engine) as session:
        yield session


def maybe_create_db_and_tables():
    # sqlite does not really work with migrations, so here we create the db fresh
    # if we are using sqlite, we are probably in the test environment
    if engine.url.drivername == "sqlite":
        SQLModel.metadata.create_all(engine)
