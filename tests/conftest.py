import os
import json
import socket
import subprocess
import time

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


def make_test_bakery_yaml(url, tempdir, real_target=False):  # TODO: switch real_target at runtime
    url = url.split("://")[1]
    if real_target:
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
    else:
        bakery_database_entry = {
            'org.test.bakery.aws.us-west-2': {
                'region': 'aws.us-west-2',  # TODO: Allow wildcard/localhost region type?
                'targets': {
                    'local-http-server': {
                        'region': 'aws.us-west-2',
                        'description': 'A local http server for testing.',
                        'public': {
                            'prefix': f'{url}/test-bakery0',
                            'protocol': 'http',
                            'storage_options': {},
                        },
                        'private': {
                            'prefix': 'test-bakery0',
                            'protocol': 'http',
                            'storage_options': {
                                "username": "{TEST_BAKERY_USERNAME}",
                                "password": "{TEST_BAKERY_PASSWORD}",
                            },
                        }
                    }
                },
                'cluster': None,
            }
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

# Fixtures -------------------------------------------------------------------


@pytest.fixture(scope="session", params=[dict()])
def bakery_http_server(tmpdir_factory, request):
    tempdir = tmpdir_factory.mktemp("test-bakery")
    zarr_local_path, ds, zarr_fname = make_zarr_local_path(tempdir)
    _, build_logs_fname, logs = make_build_logs_local_path(zarr_fname, tempdir)

    url = start_http_server(tempdir, request=request)
    http_base = f"{url}/test-bakery0"
    zarr_http_path = f"{http_base}/{zarr_fname}"
    build_logs_http_path = f"{http_base}/{build_logs_fname}"

    return url, zarr_local_path, zarr_http_path, ds, build_logs_http_path, logs


@pytest.fixture(scope="session", params=[dict()])
def github_http_server(tmpdir_factory, request, bakery_http_server):
    tempdir = tmpdir_factory.mktemp("mock-github")
    bakery_url = bakery_http_server[0]

    url = start_http_server(tempdir, request=request)
    http_base = f"{url}/mock-github0"

    bakery_database_entry = make_test_bakery_yaml(bakery_url, tempdir)
    bakery_database_http_path = f"{http_base}/test-bakery.yaml"

    return url, bakery_database_entry, bakery_database_http_path
