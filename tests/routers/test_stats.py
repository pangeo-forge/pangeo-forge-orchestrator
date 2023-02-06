import pytest

from ..helpers import create_with_dependencies
from ..model_fixtures import recipe_run_fixture


@pytest.mark.parametrize("model_fixture", [recipe_run_fixture])
def test_bakery_stats(client, authorized_client, model_fixture):
    _ = create_with_dependencies(model_fixture.create_opts[0], model_fixture, authorized_client)

    response = client.read_range("/stats/bakeries")
    assert response == {"count": 1}


@pytest.mark.parametrize("model_fixture", [recipe_run_fixture])
def test_recipe_run_stats(client, authorized_client, model_fixture):
    _ = create_with_dependencies(model_fixture.create_opts[0], model_fixture, authorized_client)

    response = client.read_range("/stats/recipe_runs")
    assert response == {"count": 1}


@pytest.mark.parametrize("query", ["", "exclude_test_runs=true"])
@pytest.mark.parametrize("model_fixture", [recipe_run_fixture])
def test_dataset_stats(client, authorized_client, model_fixture, query):
    create_response = create_with_dependencies(
        model_fixture.create_opts[0], model_fixture, authorized_client
    )

    path = f"/stats/datasets?{query}"

    response = client.read_range(path)
    assert response == {"count": 0}

    response = authorized_client.update(
        model_fixture.path, create_response["id"], model_fixture.update_opts[1]
    )

    response = client.read_range(path)
    assert response == {"count": 1}
