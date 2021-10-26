import fsspec
import xarray as xr
import yaml


def test_bakery_server(bakery_http_server):
    _, zarr_local_path, zarr_http_path, ds0 = bakery_http_server
    ds1 = xr.open_zarr(zarr_local_path, consolidated=True)
    ds2 = xr.open_zarr(zarr_http_path, consolidated=True)
    xr.testing.assert_identical(ds0, ds1)
    xr.testing.assert_identical(ds1, ds2)


def test_github_server(github_http_server):
    _, bakery_meta, bakery_meta_http_path = github_http_server

    with fsspec.open(bakery_meta_http_path) as f:
        bakery_http_meta = yaml.safe_load(f.read())

    assert bakery_http_meta == bakery_meta
