import os

from sqlmodel import SQLModel, create_engine  # noqa: F401

database_url = os.environ["DATABASE_URL"]
print(f"DATABASE_URL: {database_url}")

connect_args = {}
if database_url.startswith("sqlite:"):
    connect_args = {"check_same_thread": False}

engine = create_engine(database_url, echo=True, connect_args=connect_args)
