from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session

from ..dependencies import get_session
from ..models import MODELS

# TODO: this module is untested!
# We have deliberately accepted this techincal debt in order to get metrics up working quickly.
# Once we have some time for maintainance, we need to write tests for these endpoints.

stats_router = APIRouter()


class StatsResponse(BaseModel):
    count: int


@stats_router.get(
    "/stats/recipe_runs",
    response_model=StatsResponse,
    summary="Get statistics for recipe runs",
    tags=["stats"],
)
def get_recipe_stats(*, session: Session = Depends(get_session)):
    model = MODELS["recipe_run"]
    response = StatsResponse(count=session.query(func.count(model.table.id)).scalar())
    return response


@stats_router.get(
    "/stats/bakeries",
    response_model=StatsResponse,
    summary="Get statistics for bakeries",
    tags=["stats"],
)
def get_bakery_stats(*, session: Session = Depends(get_session)):
    model = MODELS["bakery"]
    response = StatsResponse(count=session.query(func.count(model.table.id)).scalar())
    return response


@stats_router.get(
    "/stats/feedstocks",
    response_model=StatsResponse,
    summary="Get statistics for feedstocks",
    tags=["stats"],
)
def get_feedstock_stats(*, session: Session = Depends(get_session)):
    model = MODELS["feedstock"]
    response = StatsResponse(count=session.query(func.count(model.table.id)).scalar())
    return response


@stats_router.get(
    "/stats/datasets",
    response_model=StatsResponse,
    summary="Get statistics for datasets",
    tags=["stats"],
)
def get_dataset_stats(*, session: Session = Depends(get_session)):
    model = MODELS["recipe_run"]
    response = StatsResponse(
        count=session.query(func.count(model.table.dataset_public_url)).scalar()
    )
    return response
