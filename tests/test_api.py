import pytest
from datetime import datetime

from pangeo_forge_orchestrator.model_builders import MultipleModels

from .model_fixtures import recipe_run_fixtures, CreateOpts
from .interfaces import client


def add_z(input_string: str) -> str:
    """Add a ``Z`` character the end of a timestamp string if needed, to bring it into
    compliance with ISO8601 formatting.
    """

    if not input_string.endswith("Z"):
        input_string += "Z"
    return input_string


def parse_to_datetime(input_string: str) -> datetime:
    input_string = add_z(input_string)
    return datetime.strptime(input_string, "%Y-%m-%dT%H:%M:%SZ")
    

@pytest.mark.parametrize('model,create_opts', [(recipe_run_fixtures.model, recipe_run_fixtures.create[0])])
def test_create(model: MultipleModels, create_opts: CreateOpts, client):
    data = client.create(model, create_opts.api_kwargs)

    for k, expected in create_opts.api_kwargs.items():
        actual = data[k]
        if isinstance(actual, datetime):
            assert actual == parse_to_datetime(expected)
        elif (
            # Pydantic requires a "Z"-terminated timestamp, but FastAPI responds without the "Z"
            isinstance(actual, str)
            and isinstance(expected, str)
            and any([s.endswith("Z") for s in (actual, expected)])
            and not all([s.endswith("Z") for s in (actual, expected)])
        ):
            assert add_z(actual) == add_z(expected)
        else:
            assert actual == expected
    assert data["id"] is not None
