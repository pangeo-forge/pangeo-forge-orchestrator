import ast
import copy
import json
import os
import subprocess
from typing import Optional

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

from pangeo_forge_orchestrator.client import Client

ENTRYPOINTS = ["db", "client", "cli"]


def get_data_from_cli(
    request_type: str, database_url: str, endpoint: str, request: Optional[dict] = None,
):
    os.environ["PANGEO_FORGE_DATABASE_URL"] = database_url
    cmd = ["pangeo-forge", request_type, endpoint]
    if request is not None:
        cmd.append(json.dumps(request))
    stdout = subprocess.check_output(cmd)
    data = ast.literal_eval(stdout.decode("utf-8"))
    return data


def commit_to_session(session: Session, model: SQLModel):
    session.add(model)
    session.commit()


def clear_table(session: Session, table_model: SQLModel):
    session.query(table_model).delete()
    session.commit()
    # make sure the database is empty
    assert len(session.query(table_model).all()) == 0


# Test create ---------------------------------------------------------------------------


@pytest.mark.parametrize("entrypoint", ["db"])  # ENTRYPOINTS)
def test_create(session, model_to_create, entrypoint, http_server):
    models, request, blank_opts = model_to_create
    # make sure the database is empty
    clear_table(session, models.table)

    # get response data
    # write respones to dict to make sure `data` is in fact collected
    # from a specific endpoint, as opposed to carried over from a previous test call
    # (the latter seems like it shouldn't happen, but... it seemed like it might've been?)
    r = dict()
    if entrypoint == "db":
        model = models.table(**request)
        commit_to_session(session, model)
        # Need to `get` b/c db doesn't return a response
        model_db = session.get(models.table, model.id)
        data = model_db.dict()
        r.update({entrypoint: data})
    elif entrypoint == "client":
        client = Client(base_url=http_server)
        response = client.post(models.path, json=request)
        assert response.status_code == 200
        data = response.json()
        r.update({entrypoint: data})
    elif entrypoint == "cli":
        data = get_data_from_cli("post", http_server, models.path, request)
        r.update({entrypoint: data})

    # evaluate data
    for k in request.keys():
        assert r[entrypoint][k] == request[k]
    if blank_opts:
        for k in blank_opts:
            assert r[entrypoint][k] is None
    assert r[entrypoint]["id"] is not None


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_create_incomplete(session, model_to_create, entrypoint, http_server):
    models, request, _ = model_to_create
    # make sure the database is empty
    clear_table(session, models.table)

    incomplete_request = copy.deepcopy(request)
    # Remove a required field
    del incomplete_request[list(incomplete_request)[0]]

    if entrypoint == "db":
        model = models.table(**incomplete_request)
        with pytest.raises(IntegrityError):
            commit_to_session(session, model)
    elif entrypoint == "client":
        client = Client(base_url=http_server)
        response = client.post(models.path, json=incomplete_request)
        assert response.status_code == 422
    elif entrypoint == "cli":
        data = get_data_from_cli("post", http_server, models.path, incomplete_request)
        error = data["detail"][0]
        assert error["msg"] == "field required"
        assert error["type"] == "value_error.missing"


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_create_invalid(session, model_to_create, entrypoint, http_server):
    models, request, _ = model_to_create
    # make sure the database is empty
    clear_table(session, models.table)

    assert type(request[list(request)[0]]) == str
    invalid_request = copy.deepcopy(request)
    invalid_request[list(invalid_request)[0]] = {"message": "Is this wrong?"}
    assert type(invalid_request[list(invalid_request)[0]]) == dict

    if entrypoint == "db":
        model = models.table(**invalid_request)
        # Passing an invalid field to the table model results in Pydantic silently dropping it.
        # Therefore, "invalid" requests are raised as `Integrity` i.e. missing data errors.
        with pytest.raises(IntegrityError):
            commit_to_session(session, model)
    elif entrypoint == "client":
        client = Client(base_url=http_server)
        response = client.post(models.path, json=invalid_request)
        assert response.status_code == 422
    elif entrypoint == "cli":
        data = get_data_from_cli("post", http_server, models.path, invalid_request)
        error = data["detail"][0]
        assert error["msg"] == "str type expected"  # TODO: Generalize to all msg types
        assert error["type"] == "type_error.str"  # TODO: Generalize to all error types


# Test read -----------------------------------------------------------------------------


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_read_range(session, models_to_read, entrypoint, http_server):
    models, tables = models_to_read
    # make sure the database is empty
    clear_table(session, models.table)
    # add entries for this test
    for t in tables:
        commit_to_session(session, t)

    r = dict()
    if entrypoint == "db":
        data = session.query(models.table).all()
        r.update({entrypoint: data})
    elif entrypoint == "client":
        data = session.query(models.table).all()
        client = Client(base_url=http_server)
        response = client.get(models.path)
        assert response.status_code == 200
        data = response.json()
        r.update({entrypoint: data})
    elif entrypoint == "cli":
        data = get_data_from_cli("get", http_server, models.path)
        r.update({entrypoint: data})

    assert len(r[entrypoint]) == len(tables)
    for i, t in enumerate(tables):
        input_data = t.dict()
        # `session.query` returns a list of `SQLModel` table instances
        # ... but `client.get` returns a list of `dict`s, so:
        response_data = (
            r[entrypoint][i].dict() if type(r[entrypoint][i]) != dict else r[entrypoint][i]
        )
        for k in input_data.keys():
            assert response_data[k] == input_data[k]


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_read_single(session, single_model_to_read, entrypoint, http_server):
    models, table = single_model_to_read
    # make sure the database is empty
    clear_table(session, models.table)

    commit_to_session(session, table)

    r = dict()
    if entrypoint == "db":
        model_db = session.get(models.table, table.id)
        data = model_db.dict()
        r.update({entrypoint: data})
    elif entrypoint == "client":
        client = Client(base_url=http_server)
        response = client.get(f"{models.path}{table.id}")
        assert response.status_code == 200
        data = response.json()
        r.update({entrypoint: data})
    elif entrypoint == "cli":
        data = get_data_from_cli("get", http_server, f"{models.path}{table.id}")
        r.update({entrypoint: data})

    input_dict = table.dict()
    for k in input_dict.keys():
        assert r[entrypoint][k] == input_dict[k]


# Test update ---------------------------------------------------------------------------


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_update(session, model_to_update, entrypoint, http_server):
    models, table, update_with = model_to_update
    # make sure the database is empty
    clear_table(session, models.table)
    # add entries for this test
    commit_to_session(session, table)

    r = dict()
    if entrypoint == "db":
        model_db = session.query(models.table).first()
        for k, v in update_with.items():
            setattr(model_db, k, v)
        session.commit()
        model_db = session.get(models.table, table.id)
        data = model_db.dict()
        r.update({entrypoint: data})
    elif entrypoint == "client":
        client = Client(base_url=http_server)
        response = client.patch(f"{models.path}{table.id}", json=update_with)
        assert response.status_code == 200
        data = response.json()
        r.update({entrypoint: data})
    elif entrypoint == "cli":
        data = get_data_from_cli("patch", http_server, f"{models.path}{table.id}", update_with)
        r.update({entrypoint: data})

    assert r[entrypoint]["id"] == table.id
    input_dict = table.dict()
    for k in input_dict.keys():
        if k == list(update_with)[0]:
            assert r[entrypoint][k] == update_with[k]
        else:
            assert r[entrypoint][k] == input_dict[k]


# Test delete ---------------------------------------------------------------------------


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_delete(session, model_to_delete, entrypoint, http_server):
    models, table = model_to_delete
    # make sure the database is empty
    clear_table(session, models.table)
    # add entries for this test
    commit_to_session(session, table)

    model_in_db = session.get(models.table, table.id)
    assert model_in_db is not None
    assert model_in_db == table

    if entrypoint == "db":
        clear_table(session, models.table)
        model_in_db = session.get(models.table, table.id)
        assert model_in_db is None
    elif entrypoint == "client":
        client = Client(base_url=http_server)
        delete_response = client.delete(f"{models.path}{table.id}")
        assert delete_response.status_code == 200  # successfully deleted
        get_response = client.get(f"{models.path}{table.id}")
        assert get_response.status_code == 404  # not found, b/c deleted
    elif entrypoint == "cli":
        delete_response = get_data_from_cli("delete", http_server, f"{models.path}{table.id}")
        assert delete_response == {"ok": True}  # successfully deleted
        get_response = get_data_from_cli("get", http_server, f"{models.path}{table.id}")
        assert get_response == {"detail": f"{models.table.__name__} not found"}
