from fastapi import FastAPI
from sqlmodel import Session

from .database import create_db_and_tables, engine
from .model_builders import register_endpoints
from .models import MODELS

app = FastAPI()


def get_session():
    with Session(engine) as session:
        yield session


@app.on_event("startup")
def on_startup():
    print("STARTING UP!")
    # `SQLModel` registration logic requires that we import `models` before creating the database.
    # This works fine now but leaving this link here to avoid confusion in a future refactor:
    # https://sqlmodel.tiangolo.com/tutorial/code-structure/#order-matters
    create_db_and_tables()


for k in MODELS.keys():
    register_endpoints(app, models=MODELS[k], get_session=get_session)
