import pytest

from .helpers import compare_response, create_with_dependencies
from .model_fixtures import ALL_MODEL_FIXTURES, APIOpts

create_params = [(create_opts, mf) for mf in ALL_MODEL_FIXTURES for create_opts in mf.create_opts]


@pytest.mark.parametrize("create_opts,model_fixture", create_params)
def test_create(create_opts: APIOpts, model_fixture, client):
    with client.auth_required():
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
    with pytest.raises(client.error_cls, match="422 Client Error: Unprocessable Entity"):
        with client.auth_required():
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
    with pytest.raises(client.error_cls, match="422 Client Error: Unprocessable Entity"):
        with client.auth_required():
            _ = client.create(model_fixture.path, create_kwargs)


@pytest.mark.parametrize("model_fixture", ALL_MODEL_FIXTURES)
def test_read_range(model_fixture, client, authorized_client):
    # first create some data
    path = model_fixture.path
    for i, create_opts in enumerate(model_fixture.create_opts):
        if i == 0:  # don't create same dependencies more than once
            create_with_dependencies(create_opts, model_fixture, authorized_client)
        else:
            authorized_client.create(path, create_opts)
    response = client.read_range(path)
    for expected, actual in zip(model_fixture.create_opts, response):
        compare_response(expected, actual)
        assert actual["id"] > 0


@pytest.mark.parametrize("model_fixture", ALL_MODEL_FIXTURES)
def test_read_single(model_fixture, client, authorized_client):
    # first create some data
    path = model_fixture.path
    for create_opts in model_fixture.create_opts:

        create_response = create_with_dependencies(create_opts, model_fixture, authorized_client)

        for rel in model_fixture.optional_relations:
            create_with_dependencies(
                rel.model_fixture.create_opts[0], rel.model_fixture, authorized_client
            )

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
                    relation.model_fixture.create_opts[0],
                    read_response[relation.field_name],
                )


@pytest.mark.parametrize("model_fixtures", ALL_MODEL_FIXTURES)
def test_read_nonexistent(model_fixtures, client):
    # first create some data
    path = model_fixtures.path
    id = 99999999  # an id that we are pretty sure does not exist in the db!
    with pytest.raises(client.error_cls):
        _ = client.read_single(path, id)


@pytest.mark.parametrize("create_opts,invalid_arg,model_fixture", create_params_invalid)
def test_update_invalid(
    create_opts: APIOpts, invalid_arg, model_fixture, client, authorized_client
):
    response = create_with_dependencies(create_opts, model_fixture, authorized_client)
    id = response["id"]
    with pytest.raises(client.error_cls):
        with client.auth_required():
            _ = client.update(model_fixture.path, id, invalid_arg)


update_params = [
    (create_opts, invalid_opt, mf)
    for mf in ALL_MODEL_FIXTURES
    for create_opts in mf.create_opts[:1]  # just use the first create fixture
    for invalid_opt in mf.update_opts
]


@pytest.mark.parametrize("create_opts,update_opts,model_fixture", update_params)
def test_update(create_opts: APIOpts, update_opts, model_fixture, client, authorized_client):
    create_response = create_with_dependencies(create_opts, model_fixture, authorized_client)
    id = create_response["id"]
    with client.auth_required():
        response = client.update(model_fixture.path, id, update_opts)
    compare_response(update_opts, response)


@pytest.mark.parametrize("create_opts,model_fixture", create_params)
def test_delete(create_opts: APIOpts, model_fixture, client, authorized_client):
    data = create_with_dependencies(create_opts, model_fixture, authorized_client)
    id = data["id"]
    with client.auth_required():
        _ = client.delete(model_fixture.path, id)
    with pytest.raises(client.error_cls):
        _ = client.read_single(model_fixture.path, id)


@pytest.mark.parametrize("model_fixtures", ALL_MODEL_FIXTURES)
def test_delete_invalid(model_fixtures, client):
    id = 99999999
    with pytest.raises(client.error_cls):
        with client.auth_required():
            _ = client.delete(model_fixtures.path, id)
