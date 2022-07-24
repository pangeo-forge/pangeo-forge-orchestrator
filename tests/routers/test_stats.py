def test_bakery_stats(fastapi_test_crud_client):
    client = fastapi_test_crud_client.client
    response = client.get("/stats/bakeries")
    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_recipe_run_stats(fastapi_test_crud_client):
    client = fastapi_test_crud_client.client
    response = client.get("/stats/recipe_runs")
    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_dataset_stats(fastapi_test_crud_client):
    client = fastapi_test_crud_client.client
    path = "/stats/datasets"
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"count": 0}
