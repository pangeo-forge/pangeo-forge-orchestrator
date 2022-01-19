from fastapi import FastAPI
from sqlmodel import Session

from .database import engine
from .model_builders import register_endpoints
from .models import MODELS

app = FastAPI()


def get_session():
    with Session(engine) as session:
        yield session


for k in MODELS.keys():
    register_endpoints(app, models=MODELS[k], get_session=get_session)
