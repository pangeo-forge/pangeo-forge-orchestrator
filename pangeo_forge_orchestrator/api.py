from fastapi import FastAPI
from sqlmodel import Session

# https://sqlmodel.tiangolo.com/tutorial/code-structure/#order-matters
from .abstractions import register_endpoints
from .database import create_db_and_tables, engine
from .models import MODELS

api = FastAPI()


def get_session():
    with Session(engine) as session:
        yield session


@api.on_event("startup")
def on_startup():
    create_db_and_tables()


register_endpoints(api, models=MODELS["hero"], get_session=get_session)
