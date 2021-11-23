import ast
import copy
import json
import os
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from pangeo_forge_orchestrator.client import Client
from pangeo_forge_orchestrator.models import Hero


def get_data_from_cli(database_url, endpoint, request):
    os.environ["PANGEO_FORGE_DATABASE_URL"] = database_url
    cmd = ["pangeo-forge", "post", endpoint, json.dumps(request)]
    stdout = subprocess.check_output(cmd)
    data = ast.literal_eval(stdout.decode("utf-8"))
    return data


# Test create ---------------------------------------------------------------------------


@pytest.mark.parametrize("entrypoint", ["api", "client", "cli"])
def test_create(client, create_request, entrypoint, http_server):
    endpoint, request, blank_opts = create_request
    client = client if entrypoint == "api" else Client(base_url=http_server)

    # get response data
    if entrypoint != "cli":
        response = client.post(endpoint, json=request)
        assert response.status_code == 200
        data = response.json()
    else:
        data = get_data_from_cli(http_server, endpoint, request)

    # evaluate data
    for k in request.keys():
        assert data[k] == request[k]
    if blank_opts:
        for k in blank_opts:
            assert data[k] is None
    assert data["id"] is not None


@pytest.mark.parametrize("entrypoint", ["api", "client", "cli"])
def test_create_incomplete(client, create_request, entrypoint, http_server):
    endpoint, request, _ = create_request
    client = client if entrypoint == "api" else Client(base_url=http_server)
    incomplete_request = copy.deepcopy(request)
    del incomplete_request[list(incomplete_request)[0]]

    if entrypoint != "cli":
        response = client.post(endpoint, json=incomplete_request)
        assert response.status_code == 422
    else:
        data = get_data_from_cli(http_server, endpoint, incomplete_request)
        error = data["detail"][0]
        assert error["msg"] == "field required"
        assert error["type"] == "value_error.missing"


@pytest.mark.parametrize("entrypoint", ["api", "client", "cli"])
def test_create_invalid(client, create_request, entrypoint, http_server):
    endpoint, request, _ = create_request
    client = client if entrypoint == "api" else Client(base_url=http_server)

    assert type(request[list(request)[0]]) == str
    invalid_request = copy.deepcopy(request)
    invalid_request[list(invalid_request)[0]] = {"message": "Is this wrong?"}
    assert type(invalid_request[list(invalid_request)[0]]) == dict

    if entrypoint != "cli":
        response = client.post(endpoint, json=invalid_request)
        assert response.status_code == 422
    else:
        data = get_data_from_cli(http_server, endpoint, invalid_request)
        error = data["detail"][0]
        assert error["msg"] == "str type expected"
        assert error["type"] == "type_error.str"


# Test read -----------------------------------------------------------------------------


def commit_to_session(session: Session, model: SQLModel):
    session.add(model)
    session.commit()


def test_read_range(session: Session, client: TestClient, models_to_read):
    endpoint, models = models_to_read
    for m in models:
        commit_to_session(session, m)

    response = client.get(endpoint)
    data = response.json()

    assert response.status_code == 200

    assert len(data) == len(models)
    for i, m in enumerate(models):
        model_dict = m.dict()
        for k in model_dict.keys():
            assert data[i][k] == model_dict[k]


def test_read_single(session: Session, client: TestClient, single_model_to_read):
    endpoint, model = single_model_to_read

    commit_to_session(session, model)

    response = client.get(f"{endpoint}{model.id}")
    data = response.json()

    assert response.status_code == 200

    model_dict = model.dict()
    for k in model_dict.keys():
        assert data[k] == model_dict[k]


def test_update_hero(session: Session, client: TestClient):
    hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
    session.add(hero_1)
    session.commit()

    response = client.patch(f"/heroes/{hero_1.id}", json={"name": "Deadpuddle"})
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "Deadpuddle"
    assert data["secret_name"] == "Dive Wilson"
    assert data["age"] is None
    assert data["id"] == hero_1.id


def test_delete_hero(session: Session, client: TestClient):
    hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
    session.add(hero_1)
    session.commit()

    response = client.delete(f"/heroes/{hero_1.id}")

    hero_in_db = session.get(Hero, hero_1.id)

    assert response.status_code == 200

    assert hero_in_db is None
