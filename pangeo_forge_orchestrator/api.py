from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Session, SQLModel, select

# https://sqlmodel.tiangolo.com/tutorial/code-structure/#order-matters
from .database import create_db_and_tables, engine
from .models import Hero, HeroCreate, HeroRead, HeroUpdate

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


# Specific API implementation -------------------------------------------------------------

LIMIT = Query(default=100, lte=100)


@api.post("/heroes/", response_model=HeroRead)
def create_hero(*, session: Session = Depends(get_session), hero: HeroCreate):
    return create(session=session, table_cls=Hero, model=hero)


@api.get("/heroes/", response_model=List[HeroRead])
def read_heroes(*, session: Session = Depends(get_session), offset: int = 0, limit: int = LIMIT):
    return read_range(session=session, table_cls=Hero, offset=offset, limit=limit)


@api.get("/heroes/{hero_id}", response_model=HeroRead)
def read_hero(*, session: Session = Depends(get_session), hero_id: int):
    return read_single(session=session, table_cls=Hero, id=hero_id)


@api.patch("/heroes/{hero_id}", response_model=HeroRead)
def update_hero(*, session: Session = Depends(get_session), hero_id: int, hero: HeroUpdate):
    return update(session=session, table_cls=Hero, id=hero_id, model=hero)


@api.delete("/heroes/{hero_id}")
def delete_hero(*, session: Session = Depends(get_session), hero_id: int):
    return delete(session=session, table_cls=Hero, id=hero_id)
