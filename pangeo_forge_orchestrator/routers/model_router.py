import types
from dataclasses import dataclass
from typing import Callable, List, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Relationship, Session, SQLModel, select

from ..dependencies import check_authentication_header, get_session
from ..models import MODELS

QUERY_LIMIT = Query(default=100, lte=100)

router = APIRouter()

for model_name, model in MODELS.items():

    @router.post(model.path, response_model=model.response)
    def create(
        *,
        new_model: model.creation,  # type: ignore
        session: Session = Depends(get_session),
        authorized_user=Depends(check_authentication_header),
    ):
        db_model = model.table.from_orm(new_model)
        session.add(db_model)
        session.commit()
        session.refresh(db_model)
        return db_model

    @router.get(model.path, response_model=List[model.response])
    def read_range(
        *, session: Session = Depends(get_session), offset: int = 0, limit: int = QUERY_LIMIT,
    ):
        return session.exec(select(model.table).offset(offset).limit(limit)).all()

    @router.get(model.path + "{id}", response_model=model.response)
    def read_single(*, id: int, session: Session = Depends(get_session)):
        db_model = session.get(model.table, id)
        if not db_model:
            raise HTTPException(status_code=404, detail=f"{model_name} not found")
        return db_model

    @router.patch(model.path + "{id}", response_model=model.response)
    def update(
        *,
        id: int,
        updated_model: model.update,  # type: ignore
        session: Session = Depends(get_session),
        authorized_user=Depends(check_authentication_header),
    ):
        db_model = session.get(model.table, id)
        if not db_model:
            # TODO: add test coverage for this
            raise HTTPException(status_code=404, detail=f"{model_name} not found")
        model_data = updated_model.dict(exclude_unset=True)
        for key, value in model_data.items():
            setattr(db_model, key, value)
        session.add(db_model)
        session.commit()
        session.refresh(db_model)
        return db_model

    @router.delete(model.path + "{id}")
    def delete(
        *,
        id: int,
        session: Session = Depends(get_session),
        authorized_user=Depends(check_authentication_header),
    ):
        return delete(session=session, table_cls=model.table, id=id)
        db_model = session.get(model.table, id)
        if not db_model:
            raise HTTPException(status_code=404, detail=f"{model_name} not found")
        session.delete(db_model)
        session.commit()
        return {"ok": True}
