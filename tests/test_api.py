from datetime import datetime

import pytest

from pangeo_forge_orchestrator.model_builders import MultipleModels

from .interfaces import client  # noqa: F401
from .model_fixtures import ALL_MODEL_FIXTURES, APIOpts


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


create_params = [
    (mf.model, create_opts) for mf in ALL_MODEL_FIXTURES for create_opts in mf.create_opts
]


@pytest.mark.parametrize("model,create_opts", create_params)
def test_create(model: MultipleModels, create_opts: APIOpts, client):
    data = client.create(model, create_opts)

    for k, expected in create_opts.items():
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


create_params_incomplete = [
    (mf.model, create_opts, required_arg)
    for mf in ALL_MODEL_FIXTURES
    for create_opts in mf.create_opts[:1]  # just use the first create fixture
    for required_arg in mf.required_fields
]


@pytest.mark.parametrize("model,create_opts,required_arg", create_params_incomplete)
def test_create_incomplete(model: MultipleModels, create_opts: APIOpts, required_arg: str, client):
    create_kwargs = create_opts.copy()
    del create_kwargs[required_arg]
    with pytest.raises(client.error_cls) as err:
        _ = client.create(model, create_kwargs)


create_params_invalid = [
    (mf.model, create_opts, invalid_opt)
    for mf in ALL_MODEL_FIXTURES
    for create_opts in mf.create_opts[:1]  # just use the first create fixture
    for invalid_opt in mf.invalid_opts
]


@pytest.mark.parametrize("model,create_opts,invalid_arg", create_params_invalid)
def test_create_invalid(model: MultipleModels, create_opts: APIOpts, invalid_arg, client):
    create_kwargs = create_opts.copy()
    create_kwargs.update(invalid_arg)
    with pytest.raises(client.error_cls):
        _ = client.create(model, create_kwargs)
