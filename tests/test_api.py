from datetime import datetime

import pytest

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


def compare_response(response_fixture, reponse_data):
    for k, expected in response_fixture.items():
        actual = reponse_data[k]
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


def create_with_dependencies(create_opts, mf, client):

    # the dependencies themselves might have "inner" dependencies of their own;
    # e.g., `dataset` depends on `recipe_run` which depends on `feedstock` and `bakery`
    dependencies = [dict(inner=d.model_fixture.dependencies, outer=d) for d in mf.dependencies]

    def _create_dep(dep, client):
        dep_create_opts = dep.model_fixture.create_opts[0]  # just use first create_opts
        dep_create_response = client.create(dep.model_fixture.path, dep_create_opts)
        compare_response(dep_create_opts, dep_create_response)

    for deps in dependencies:
        if deps["inner"]:
            for d in deps["inner"]:
                _create_dep(d, client)

        _create_dep(deps["outer"], client)

    data = client.create(mf.path, create_opts)

    return data


create_params = [(create_opts, mf) for mf in ALL_MODEL_FIXTURES for create_opts in mf.create_opts]


@pytest.mark.parametrize("create_opts,model_fixture", create_params)
def test_create(create_opts: APIOpts, model_fixture, client):

    data = create_with_dependencies(create_opts, model_fixture, client)

    compare_response(create_opts, data)
    assert data["id"] > 0


create_params_incomplete = [
    (mf.path, create_opts, required_arg)
    for mf in ALL_MODEL_FIXTURES
    for create_opts in mf.create_opts[:1]  # just use the first create fixture
    for required_arg in mf.required_fields
]


@pytest.mark.parametrize("path,create_opts,required_arg", create_params_incomplete)
def test_create_incomplete(path: str, create_opts: APIOpts, required_arg: str, client):
    create_kwargs = create_opts.copy()
    del create_kwargs[required_arg]
    with pytest.raises(client.error_cls):
        _ = client.create(path, create_kwargs)


create_params_invalid = [
    (create_opts, invalid_opt, mf)
    for mf in ALL_MODEL_FIXTURES
    for create_opts in mf.create_opts[:1]  # just use the first create fixture
    for invalid_opt in mf.invalid_opts
]


@pytest.mark.parametrize("create_opts,invalid_arg,model_fixture", create_params_invalid)
def test_create_invalid(create_opts: APIOpts, invalid_arg, model_fixture, client):
    create_kwargs = create_opts.copy()
    create_kwargs.update(invalid_arg)
    with pytest.raises(client.error_cls):
        _ = client.create(model_fixture.path, create_kwargs)


@pytest.mark.parametrize("model_fixture", ALL_MODEL_FIXTURES)
def test_read_range(model_fixture, client):
    # first create some data
    path = model_fixture.path
    for i, create_opts in enumerate(model_fixture.create_opts):
        if i == 0:  # don't create same dependencies more than once
            create_with_dependencies(create_opts, model_fixture, client)
        else:
            client.create(model_fixture.path, create_opts)

    response = client.read_range(path)
    for expected, actual in zip(model_fixture.create_opts, response):
        compare_response(expected, actual)
        assert actual["id"] > 0


@pytest.mark.parametrize("model_fixture", ALL_MODEL_FIXTURES)
def test_read_single(model_fixture, client):
    # first create some data
    path = model_fixture.path
    for create_opts in model_fixture.create_opts:

        create_response = create_with_dependencies(create_opts, model_fixture, client)

        for rel in model_fixture.optional_relations:
            create_with_dependencies(rel.model_fixture.create_opts[0], rel.model_fixture, client)

        read_response = client.read_single(path, create_response["id"])
        compare_response(create_opts, read_response)
        assert read_response["id"] == create_response["id"]

        # `compare_response` iterates over fixture keys, so we need to eval relations separately
        for relation in model_fixture.all_relations:
            if isinstance(read_response[relation.field_name], list):  # maybe one-to-many
                for resp in read_response[relation.field_name]:  # TODO: Test len(list) > 1
                    compare_response(relation.model_fixture.create_opts[0], resp)
            else:
                compare_response(
                    relation.model_fixture.create_opts[0], read_response[relation.field_name],
                )


@pytest.mark.parametrize("model_fixtures", ALL_MODEL_FIXTURES)
def test_read_nonexistent(model_fixtures, client):
    # first create some data
    path = model_fixtures.path
    id = 99999999  # an id that we are pretty sure does not exist in the db!
    with pytest.raises(client.error_cls):
        _ = client.read_single(path, id)


@pytest.mark.parametrize("create_opts,invalid_arg,model_fixture", create_params_invalid)
def test_update_invalid(create_opts: APIOpts, invalid_arg, model_fixture, client):

    response = create_with_dependencies(create_opts, model_fixture, client)
    id = response["id"]
    with pytest.raises(client.error_cls):
        _ = client.update(model_fixture.path, id, invalid_arg)


update_params = [
    (create_opts, invalid_opt, mf)
    for mf in ALL_MODEL_FIXTURES
    for create_opts in mf.create_opts[:1]  # just use the first create fixture
    for invalid_opt in mf.update_opts
]


@pytest.mark.parametrize("create_opts,update_opts,model_fixture", update_params)
def test_update(create_opts: APIOpts, update_opts, model_fixture, client):

    create_response = create_with_dependencies(create_opts, model_fixture, client)
    id = create_response["id"]
    response = client.update(model_fixture.path, id, update_opts)
    compare_response(update_opts, response)


@pytest.mark.parametrize("create_opts,model_fixture", create_params)
def test_delete(create_opts: APIOpts, model_fixture, client):

    data = create_with_dependencies(create_opts, model_fixture, client)
    id = data["id"]
    _ = client.delete(model_fixture.path, id)
    with pytest.raises(client.error_cls):
        _ = client.read_single(model_fixture.path, id)


@pytest.mark.parametrize("model_fixtures", ALL_MODEL_FIXTURES)
def test_delete_invalid(model_fixtures, client):
    id = 99999999
    with pytest.raises(client.error_cls):
        _ = client.delete(model_fixtures.path, id)
