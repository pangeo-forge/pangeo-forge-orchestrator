import ast
import json
import os

import aiohttp
import pytest
import fsspec
import xarray as xr
import yaml
from aiohttp.client_exceptions import ClientResponseError
from fsspec.implementations.http import HTTPFileSystem


def write_test_file(tempdir, http_base):
    src_path = os.fspath(tempdir.join("test-src.json"))
    dst_path = f"{http_base}/test-dst.json"
    content = dict(a=1)
    with open(src_path, mode="w") as f:
        json.dump(content, f)

    cl = os.path.getsize(src_path)
    headers = {"Content-Length": str(cl)}
    return content, src_path, dst_path, headers


def test_bakery_server_zarr_store(bakery_http_server):
    _, _, zarr_local_path, zarr_http_path, ds0, _, _ = bakery_http_server
    ds1 = xr.open_zarr(zarr_local_path, consolidated=True)
    ds2 = xr.open_zarr(zarr_http_path, consolidated=True)
    xr.testing.assert_identical(ds0, ds1)
    xr.testing.assert_identical(ds1, ds2)


def test_bakery_server_build_logs(bakery_http_server):
    _, _, _, _, _, build_logs_http_path, logs = bakery_http_server

    with fsspec.open(build_logs_http_path) as f:
        build_logs_dict = json.loads(f.read())

    assert build_logs_dict == logs


@pytest.mark.parametrize("creds", [["foo", "bar"], ["foo", "b"], ["f", "bar"], "from_env"])
def test_bakery_server_put(creds, bakery_http_server):
    tempdir, http_base = bakery_http_server[:2]

    content, src_path, dst_path, cl_header = write_test_file(tempdir, http_base)

    creds = (
        creds
        if not creds == "from_env"
        else [os.environ[k] for k in ("TEST_BAKERY_USERNAME", "TEST_BAKERY_PASSWORD")]
    )
    auth = aiohttp.BasicAuth(*creds)
    auth_header = {"Authorization": auth.encode()}
    fs = HTTPFileSystem(client_kwargs={"headers": auth_header})

    if creds[0] == "foo" and creds[1] == "bar":
        fs.put(src_path, dst_path, headers=cl_header)
        r = fs.cat(dst_path)
        assert ast.literal_eval(r.decode("utf-8")) == content
    else:
        with pytest.raises(ClientResponseError):
            fs.put(src_path, dst_path, headers=cl_header)


def test_github_server(github_http_server):
    _, bakery_meta, bakery_meta_http_path = github_http_server

    with fsspec.open(bakery_meta_http_path) as f:
        bakery_http_meta = yaml.safe_load(f.read())

    assert bakery_http_meta == bakery_meta
