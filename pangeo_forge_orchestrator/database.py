import os

from sqlmodel import Session, SQLModel, create_engine  # noqa: F401

database_url = os.environ["DATABASE_URL"]

connect_args = {}
if database_url.startswith("sqlite:"):
    connect_args = {"check_same_thread": False}
elif database_url.startswith("postgres://"):  # pragma: no cover
    # Fix Heroku's incompatible postgres database uri
    # https://stackoverflow.com/a/67754795/3266235
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url, echo=True, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session


def create_sqlite_db_and_tables():
    # Called from `.api`; requires `.models` import to register metadata
    # https://sqlmodel.tiangolo.com/tutorial/create-db-and-table/#refactor-data-creation
    SQLModel.metadata.create_all(engine)
