import os

from sqlmodel import SQLModel, create_engine  # noqa: F401

database_url = os.environ["DATABASE_URL"]
print(f"DATABASE_URL: {database_url}")

connect_args = {}
if database_url.startswith("sqlite:"):
    connect_args = {"check_same_thread": False}
elif database_url.startswith("postgres://"):
    # Fix Heroku's incompatible postgres database uri
    # https://stackoverflow.com/a/67754795/3266235
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url, echo=True, connect_args=connect_args)
