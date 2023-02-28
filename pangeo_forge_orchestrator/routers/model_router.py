from typing import Literal

from fastapi import APIRouter, Query

from ..models import MODELS

QUERY_LIMIT = Query(default=100, lte=100, description="Limit the number of results")

router = APIRouter()


def make_read_range_endpoint(model):
    def read_range(
        *,
        offset: int = 0,
        limit: int = QUERY_LIMIT,
        order_by: str = Query(None, description="Order by this column"),
        sort: Literal["asc", "desc"] = Query("asc", description="Sort in this direction"),
    ):
        ...
        return ...

    return read_range


def make_read_single_endpoint(model):
    def read_single(*, id: int):
        ...

    return read_single


for model_name, model in MODELS.items():
    read_response_model = model.extended_response if model.extended_response else model.response
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


@router.get(
    "/feedstocks/{id}/datasets",
    summary="Get a list of datasets for a feedstock",
    tags=["feedstock", "public"],
)
def get_feedstock_datasets(
    id: int,
    *,
    type: Literal["all", "production", "test"] = Query(
        "all", description="Filter by whether the dataset is a production or test dataset"
    ),
):
    MODELS["recipe_run"]

    if type == "production":
        pass

    elif type == "test":
        pass

    results = ...
    return results
