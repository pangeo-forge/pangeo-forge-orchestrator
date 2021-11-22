from dataclasses import dataclass
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Session, SQLModel, select

# https://sqlmodel.tiangolo.com/tutorial/code-structure/#order-matters
from .database import create_db_and_tables, engine
from .models import MODELS, MultipleModels

api = FastAPI()


def get_session():
    with Session(engine) as session:
        yield session


@api.on_event("startup")
def on_startup():
    create_db_and_tables()


# Generalized API functions ---------------------------------------------------------------


def create(*, session: Session, table_cls: SQLModel, model: SQLModel) -> SQLModel:
    db_model = table_cls.from_orm(model)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


def read_range(*, session: Session, table_cls: SQLModel, offset: int, limit: int) -> List:
    return session.exec(select(table_cls).offset(offset).limit(limit)).all()


def read_single(*, session: Session, table_cls: SQLModel, id: int):
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    return db_model


def update(*, session: Session, table_cls: SQLModel, id: int, model: SQLModel) -> SQLModel:
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    model_data = model.dict(exclude_unset=True)
    for key, value in model_data.items():
        setattr(db_model, key, value)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


def delete(*, session: Session, table_cls: SQLModel, id: int) -> dict:
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    session.delete(db_model)
    session.commit()
    return {"ok": True}


# Endpoint generator ----------------------------------------------------------------------


@dataclass
class GenerateEndpoints:
    """From a ``MultipleModels`` object, generate create, read, update, delete (CRUD) API endpoints.

    :param model: The ``MultipleModels`` object.
    :param limit: The bounds for API read request.
    """

    model: MultipleModels
    limit: Query = Query(default=100, lte=100)

    def make_create_endpoint(self):
        @api.post(self.model.path, response_model=self.model.response)
        def endpoint(
            *, session: Session = Depends(get_session), model: self.model.creation,  # type: ignore
        ):
            return create(session=session, table_cls=self.model.table, model=model)

        return endpoint

    def make_read_range_endpoint(self):
        @api.get(self.model.path, response_model=List[self.model.response])
        def endpoint(
            *, session: Session = Depends(get_session), offset: int = 0, limit: int = self.limit,
        ):
            return read_range(
                session=session, table_cls=self.model.table, offset=offset, limit=limit
            )

        return endpoint

    def make_read_single_endpoint(self):
        @api.get(self.model.path + "{id}", response_model=self.model.response)
        def endpoint(*, session: Session = Depends(get_session), id: int):
            return read_single(session=session, table_cls=self.model.table, id=id)

        return endpoint

    def make_update_endpoint(self):
        @api.patch(self.model.path + "{id}", response_model=self.model.response)
        def endpoint(
            *,
            session: Session = Depends(get_session),
            id: int,
            model: self.model.update,  # type: ignore
        ):
            return update(session=session, table_cls=self.model.table, id=id, model=model)

        return endpoint

    def make_delete_endpoint(self):
        @api.delete(self.model.path + "{id}")
        def endpoint(*, session: Session = Depends(get_session), id: int):
            return delete(session=session, table_cls=self.model.table, id=id)

        return endpoint


# Specific API implementation -------------------------------------------------------------


hero_endpoints = GenerateEndpoints(MODELS["hero"])
create_hero = hero_endpoints.make_create_endpoint()
read_heroes = hero_endpoints.make_read_range_endpoint()
read_hero = hero_endpoints.make_read_single_endpoint()
update_hero = hero_endpoints.make_update_endpoint()
delete_hero = hero_endpoints.make_delete_endpoint()
