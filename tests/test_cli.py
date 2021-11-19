import ast
import json
import os
import subprocess


def test_create_hero(http_server, create_request):
    os.environ["PANGEO_FORGE_DATABASE_URL"] = http_server

    cmd = ["pangeo-forge", "create-hero", json.dumps(create_request)]
    stdout = subprocess.check_output(cmd)
    data = ast.literal_eval(stdout.decode("utf-8"))

    # assert response.status_code == 200
    assert data["name"] == create_request["name"]
    assert data["secret_name"] == create_request["secret_name"]
    assert data["age"] is None
    assert data["id"] is not None
