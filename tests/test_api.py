import pytest

from .helpers import compare_response, create_with_dependencies
from .model_fixtures import ALL_MODEL_FIXTURES


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


@pytest.mark.parametrize("sort", ["asc", "desc"])
@pytest.mark.parametrize("order_by", ["id"])
@pytest.mark.parametrize("model_fixture", ALL_MODEL_FIXTURES)
def test_read_range_with_sort_ordering(model_fixture, client, authorized_client, sort, order_by):
    # first create some data
    path = model_fixture.path
    for i, create_opts in enumerate(model_fixture.create_opts):
        if i == 0:  # don't create same dependencies more than once
            create_with_dependencies(create_opts, model_fixture, authorized_client)
        else:
            authorized_client.create(path, create_opts)

    path = f"{path}?offset=0&limit=100&order_by={order_by}&sort={sort}"
    response = client.read_range(path)
    for item in response:
        assert item["id"] > 0


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
