"""
This is where we put all the data about creating / updating models
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Sequence, Union

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


APIOpts = Dict[str, Union[int, str]]


@dataclass
class ModelFixtures:
    path: str
    required_fields: Sequence[str]
    create_opts: Sequence[APIOpts]  # valid ways to create the model
    invalid_opts: Sequence[APIOpts]  # setting these on creation or update should error
    update_opts: Sequence[APIOpts]  # setting these on update should be valid


NOT_STR = {"not parsable": "to str"}
NOT_INT = "not parsable to int"
NOT_ISO8601 = "Jan 01 2021 00:00:00"


recipe_run_fixtures = ModelFixtures(
    path="/recipe_runs/",
    required_fields=[
        "recipe_id",
        "bakery_id",
        "feedstock_id",
        "head_sha",
        "version",
        "started_at",
    ],
    create_opts=[
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
        dict(
            recipe_id="test-recipe-1",
            bakery_id=1,
            feedstock_id=1,
            head_sha="012345abcdefg",
            version="2.0",
            started_at="2021-02-02T00:00:00Z",
            status="queued",
        ),
    ],
    invalid_opts=[
        dict(recipe_id=NOT_STR),
        dict(bakery_id=NOT_INT),
        dict(feedstock_id=NOT_INT),
        dict(head_sha=NOT_STR),
        dict(version=NOT_STR),
        dict(started_at=NOT_ISO8601),
        dict(completed_at=NOT_ISO8601),
        dict(conclusion="not a valid conclusion"),
        dict(status="not a valid status"),
        dict(message=NOT_STR),
        # the following two options should fail but don't
        dict(id=100),  # shouldn't be able to pass id at all; instead silently ignored
        dict(random_field_that_doesnt_exist_and_shouldnt_be_allow="foobar"),
    ],
    update_opts=[
        {"completed_at": "2021-01-02T01:01:01Z", "status": "completed", "conclusion": "failure"},
        {"completed_at": "2021-01-02T01:01:01Z", "status": "completed", "conclusion": "success"},
    ],
)

ALL_MODEL_FIXTURES = [recipe_run_fixtures]
