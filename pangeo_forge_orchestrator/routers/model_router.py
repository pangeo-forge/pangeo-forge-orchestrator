from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_
from sqlalchemy.orm import load_only
from sqlmodel import Session, asc, desc, select

from ..dependencies import check_authentication_header, get_session
from ..models import MODELS

QUERY_LIMIT = Query(default=100, lte=100, description="Limit the number of results")

router = APIRouter()


def make_create_endpoint(model):
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

    return create


def make_read_range_endpoint(model):
    def read_range(
        *,
        session: Session = Depends(get_session),
        offset: int = 0,
        limit: int = QUERY_LIMIT,
        order_by: str = Query(None, description="Order by this column"),
        sort: Literal["asc", "desc"] = Query("asc", description="Sort in this direction"),
    ):
        statement = select(model.table)
        if order_by:
            column = (
                asc(getattr(model.table, order_by))
                if sort == "asc"
                else desc(getattr(model.table, order_by))
            )
            statement = statement.order_by(column)
        statement = statement.offset(offset).limit(limit)
        return session.exec(statement).all()

    return read_range


def make_read_single_endpoint(model):
    def read_single(*, id: int, session: Session = Depends(get_session)):
        db_model = session.get(model.table, id)
        if not db_model:
            raise HTTPException(status_code=404, detail=f"{model_name} not found")
        return db_model

    return read_single


def make_update_endpoint(model):
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

    return update


def make_delete_endpoint(model):
    def delete(
        *,
        id: int,
        session: Session = Depends(get_session),
        authorized_user=Depends(check_authentication_header),
    ):
        db_model = session.get(model.table, id)
        if not db_model:
            raise HTTPException(status_code=404, detail=f"{model_name} not found")
        session.delete(db_model)
        session.commit()
        return {"ok": True}

    return delete


for model_name, model in MODELS.items():
    read_response_model = model.extended_response if model.extended_response else model.response
    router.add_api_route(
        model.path,
        make_create_endpoint(model),
        methods=["POST"],
        response_model=model.response,
        summary=f"Create a single {model.descriptive_name}",
        tags=[model.descriptive_name, "admin"],
    )
    router.add_api_route(
        model.path,
        make_read_range_endpoint(model),
        methods=["GET"],
        response_model=list[model.response],  # type: ignore
        summary=f"Read a range of {model.descriptive_name} objects",
        tags=[model.descriptive_name, "public"],
    )
    router.add_api_route(
        model.path + "{id}",
        make_read_single_endpoint(model),
        methods=["GET"],
        response_model=read_response_model,
        summary=f"Read a single {model.descriptive_name}",
        tags=[model.descriptive_name, "public"],
    )
    router.add_api_route(
        model.path + "{id}",
        make_update_endpoint(model),
        methods=["PATCH"],
        response_model=model.response,
        summary=f"Update a {model.descriptive_name}",
        tags=[model.descriptive_name, "admin"],
    )
    router.add_api_route(
        model.path + "{id}",
        make_delete_endpoint(model),
        methods=["DELETE"],
        summary=f"Delete a {model.descriptive_name}",
        tags=[model.descriptive_name, "admin"],
    )


@router.get(
    "/feedstocks/{id}/datasets",
    summary="Get a list of datasets for a feedstock",
    tags=["feedstock", "public"],
)
def get_feedstock_datasets(
    id: int,
    *,
    session: Session = Depends(get_session),
    type: Literal["all", "production", "test"] = Query(
        "all", description="Filter by whether the dataset is a production or test dataset"
    ),
):
    model = MODELS["recipe_run"]

    statement = and_(
        model.table.feedstock_id == id,
        model.table.dataset_public_url.isnot(None),
        model.table.status == "completed",
        model.table.conclusion == "success",
    )

    if type == "production":
        statement = and_(statement, model.table.is_test.is_(False))

    elif type == "test":
        statement = and_(statement, model.table.is_test.is_(True))

    results = (
        session.query(model.table)
        .filter(statement)
        .options(
            load_only("recipe_id", "feedstock_id", "dataset_type", "dataset_public_url", "is_test")
        )
    )
    return results.all()
