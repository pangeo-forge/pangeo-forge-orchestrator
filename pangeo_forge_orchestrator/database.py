import os

from sqlmodel import Session, SQLModel, create_engine  # noqa: F401


def get_database_url_from_env():
    try:
        database_url = os.environ["DATABASE_URL"]
    except KeyError:  # pragma: no cover
        raise ValueError("Application can't run unless DATABASE_URL environment variable is set")
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

engine = create_engine(database_url, echo=False, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session


def create_sqlite_db_and_tables():
    # Called from `.api`; requires `.models` import to register metadata
    # https://sqlmodel.tiangolo.com/tutorial/create-db-and-table/#refactor-data-creation
    SQLModel.metadata.create_all(engine)
