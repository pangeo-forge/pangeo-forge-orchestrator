"""
This is where we put all the data about creating / updating models
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Sequence

from pangeo_forge_orchestrator.model_builders import MultipleModels
from pangeo_forge_orchestrator.models import MODELS

# Model fixture containers --------------------------------------------------------------


class APIErrors(str, Enum):
    """Error types that may occur if field input does not conform to the schema defined by the
    table's Pydantic base model.
    """

    datetime = "datetime"
    enum = "enum"
    int = "integer"
    missing = "missing"
    str = "string"


@dataclass
class CreateOpts:
    api_kwargs: Dict[str, Any]
    only_required_fields: bool = False
    error: Optional[APIErrors] = None


@dataclass
class UpdateOpts:
    api_kwargs: Dict[str, Any]
    error: Optional[APIErrors] = None


@dataclass
class ModelFixtures:
    model: MultipleModels
    create: Sequence[CreateOpts]
    update: Sequence[UpdateOpts]

NOT_STR = {"not parsable": "to str"}
NOT_INT = "not parsable to int"
NOT_ISO8601 = "Jan 01 2021 00:00:00"

recipe_run_fixtures = ModelFixtures(
    model=MODELS["recipe_run"],
    create=[
        CreateOpts(
            dict(
                recipe_id="test-recipe-0",
                bakery_id=0,
                feedstock_id=0,
                head_sha="abcdefg12345",
                version="1.0",
                started_at="2021-01-01T00:00:00Z",
                completed_at="2021-01-01T01:01:01Z",
                conclusion="success",
                status="completed",
                message="hello",
            ),
        ),
        CreateOpts(
            dict(
                recipe_id="test-recipe-1",
                bakery_id=1,
                feedstock_id=1,
                head_sha="012345abcdefg",
                version="2.0",
                started_at="2021-02-02T00:00:00Z",
                status="queued",
            ),
            only_required_fields=True
        )
    ],
    update=[
        UpdateOpts(dict(recipe_id=NOT_STR), error=APIErrors.str),
        UpdateOpts(dict(bakery_id=NOT_INT), error=APIErrors.int),
        UpdateOpts(dict(feedstock_id=NOT_INT), error=APIErrors.int),
        UpdateOpts(dict(head_sha=NOT_STR), error=APIErrors.str),
        UpdateOpts(dict(version=NOT_STR), error=APIErrors.str),  # TODO: use `ConstrainedStr`
        UpdateOpts(dict(started_at=NOT_ISO8601), error=APIErrors.datetime),
        UpdateOpts(dict(completed_at=NOT_ISO8601), error=APIErrors.datetime),
        UpdateOpts(dict(conclusion="not a valid conclusion"), error=APIErrors.enum),
        UpdateOpts(dict(status="not a valid status"), error=APIErrors.enum),
        UpdateOpts(dict(message=NOT_STR), error=APIErrors.str)
    ]
)
