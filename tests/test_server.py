import xarray as xr


def test_server(bakery_http_path):
    url, zarr_path, ds0 = bakery_http_path
    ds1 = xr.open_zarr(zarr_path, consolidated=True)
    xr.testing.assert_identical(ds0, ds1)
