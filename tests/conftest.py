import os
import json
import socket
import subprocess
import time

import aiohttp
import numpy as np
import pandas as pd
import pytest
import xarray as xr
import yaml


# Helper functions -----------------------------------------------------------


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


def start_http_server(path, request, username=None, password=None):

    basedir = path.dirpath()
    this_dir = os.path.dirname(os.path.abspath(__file__))
    port = get_open_port()
    command_list = [
        "python",
        os.path.join(this_dir, "http_auth_server.py"),
        f"--port={port}",
        "--address=127.0.0.1",
    ]
    if username:
        command_list += [f"--username={username}", f"--password={password}"]
    p = subprocess.Popen(command_list, cwd=basedir)
    url = f"http://127.0.0.1:{port}"
    time.sleep(2)  # let the server start up

    def teardown():
        p.kill()

    request.addfinalizer(teardown)

    return url


def daily_xarray_dataset():
    """Return a synthetic random xarray dataset."""
    np.random.seed(1)
    # TODO: change nt to 11 in order to catch the edge case where
    # items_per_input does not evenly divide the length of the sequence dimension
    nt, ny, nx = 10, 18, 36
    time = pd.date_range(start="2010-01-01", periods=nt, freq="D")
    lon = (np.arange(nx) + 0.5) * 360 / nx
    lon_attrs = {"units": "degrees_east", "long_name": "longitude"}
    lat = (np.arange(ny) + 0.5) * 180 / ny
    lat_attrs = {"units": "degrees_north", "long_name": "latitude"}
    foo = np.random.rand(nt, ny, nx)
    foo_attrs = {"long_name": "Fantastic Foo"}
    # make sure things work with heterogenous data types
    bar = np.random.randint(0, 10, size=(nt, ny, nx))
    bar_attrs = {"long_name": "Beautiful Bar"}
    dims = ("time", "lat", "lon")
    ds = xr.Dataset(
        {"bar": (dims, bar, bar_attrs), "foo": (dims, foo, foo_attrs)},
        coords={
            "time": ("time", time),
            "lat": ("lat", lat, lat_attrs),
            "lon": ("lon", lon, lon_attrs),
        },
        attrs={"conventions": "CF 1.6"},
    )
    return ds


def make_zarr_local_path(tempdir):
    ds = daily_xarray_dataset()
    fname = "test-dataset.zarr"
    zarr_path = tempdir.join(fname)
    ds.to_zarr(zarr_path, consolidated=True)
    return zarr_path, ds, fname


def make_test_bakery_yaml(http_base, tempdir, real_target=False):
    http_base = http_base.split("://")[1]
    if real_target:  # TODO: switch real_target at runtime
        bakery_database_entry = {
            'org.test-osn.bakery.aws.us-west-2': {
                'region': 'aws.us-west-2',
                'targets': {
                    'osn': {
                        'region': 'aws.us-west-2',
                        'description': 'Open Storage Network (OSN) bucket',
                        'public': {
                            'prefix': 'Pangeo/pangeo-forge',
                            'protocol': 's3',
                            'storage_options': {
                                'anon': True,
                                'client_kwargs': {
                                    'endpoint_url': 'https://ncsa.osn.xsede.org'
                                }
                            }
                        },
                        'private': {
                            'prefix': 'Pangeo/pangeo-forge',
                            'protocol': 's3',
                            'storage_options': {
                                'key': '{OSN_KEY}',
                                'secret': '{OSN_SECRET}',
                                'client_kwargs': {
                                    'endpoint_url': 'https://ncsa.osn.xsede.org'
                                },
                                'default_cache_type': 'none',
                                'default_fill_cache': False,
                                'use_listings_cache': False,
                            }
                        }
                    }
                },
                'cluster': None,
            }
        }
    elif not real_target:
        bakery_database_entry = {
            'org.test.bakery.aws.us-west-2': {
                'region': 'aws.us-west-2',  # TODO: Allow wildcard/localhost region type?
                'targets': {
                    'local-http-server': {
                        'region': 'aws.us-west-2',
                        'description': 'A local http server for testing.',
                        'public': {
                            'prefix': f'{http_base}',
                            'protocol': 'http',
                            'storage_options': {},
                        },
                        'private': {
                            'prefix': f'{http_base}',
                            'protocol': 'http',
                            'storage_options': {
                                "client_kwargs": {
                                    "headers": {
                                        "Authorization": "{TEST_BAKERY_BASIC_AUTH}",
                                    },
                                },
                            },
                        },
                    },
                },
                'cluster': None,
            },
        }
    with open(f"{tempdir}/test-bakery.yaml", mode="w") as f:
        f.write(yaml.dump(bakery_database_entry))

    return bakery_database_entry


def make_build_logs_local_path(zarr_fname, tempdir):
    fname = "build-logs.json"
    logs = {
        "00000": {
            "timestamp": "2021-09-25 00:00:00",
            "feedstock": "mock-feedstock@1.0",
            "recipe": "recipe",
            "path": zarr_fname,
        }
    }
    local_path = tempdir.join(fname)
    with open(local_path, mode="w") as f:
        json.dump(logs, f)

    return local_path, fname, logs


def make_meta_yaml_local_path(tempdir):
    meta_yaml = {
        "title": "Mock Feedstock",
        "description": "Random test data.",
        "pangeo_forge_version": "0.6.1",
        "pangeo_notebook_version": "2021.07.17",
        "recipes": [
            {
                "id": "mock-feedstock",
                "object": "recipe",
            },
        ],
        "provenance": {
            "providers": [
                {
                    "name": "NumPy Random",
                    "description": "NumPy random data.",
                    "roles": ["producer", "licensor"],
                    "url": "https://pangeo-forge-random-data.org",
                    "license": "CC-BY-4.0"
                }
            ],
        },
        "maintainers": [
            {
                "name": "Awesome Pangeo Forge Contributor",
                "orcid": "0000-0000-0000-0000",
                "github": "awpfc",
            }
        ],
        "bakery": {
            "id": "org.test.bakery.aws.us-west-2",  # must come from a valid list of bakeries
            "target": "local-http-server",
            "resources": {
                "memory": 4096,
                "cpu": 1024,
            }
        }
    }
    with open(f"{tempdir}/meta.yaml", mode="w") as f:
        f.write(yaml.dump(meta_yaml))


# Fixtures -------------------------------------------------------------------


@pytest.fixture(scope="session", params=[dict()])
def bakery_http_server(tmpdir_factory, request):
    tempdir = tmpdir_factory.mktemp("test-bakery")
    zarr_local_path, ds, zarr_fname = make_zarr_local_path(tempdir)
    _, build_logs_fname, logs = make_build_logs_local_path(zarr_fname, tempdir)

    username, password = "foo", "bar"
    # plain text env vars for `test_server::test_bakery_server_put`
    os.environ["TEST_BAKERY_USERNAME"] = username
    os.environ["TEST_BAKERY_PASSWORD"] = password
    # encoded env var for `test_components::test_bakery_component_write_access`
    auth = aiohttp.BasicAuth(username, password)
    os.environ["TEST_BAKERY_BASIC_AUTH"] = auth.encode()

    url = start_http_server(tempdir, request=request, username=username, password=password)
    http_base = f"{url}/test-bakery0"
    zarr_http_path = f"{http_base}/{zarr_fname}"
    build_logs_http_path = f"{http_base}/{build_logs_fname}"

    return tempdir, http_base, zarr_local_path, zarr_http_path, ds, build_logs_http_path, logs


@pytest.fixture(scope="session", params=[dict()])
def github_http_server(tmpdir_factory, request, bakery_http_server):
    tempdir_0 = tmpdir_factory.mktemp("mock-github")

    # TODO: generate path from feedstock in `build-logs.json`; probably make `logs` dict a fixture.
    meta_path = tempdir_0 / "pangeo-forge" / "mock-feedstock" / "v1.0" / "feedstock"
    os.makedirs(meta_path)

    make_meta_yaml_local_path(meta_path)

    url = start_http_server(tempdir_0, request=request)
    http_base = f"{url}/mock-github0"

    bakery_url = bakery_http_server[1]
    bakery_database_entry = make_test_bakery_yaml(bakery_url, tempdir_0)
    bakery_database_http_path = f"{http_base}/test-bakery.yaml"

    return http_base, bakery_database_entry, bakery_database_http_path
