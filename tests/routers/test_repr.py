def test_xarray_repr(client):
    url = "https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/HadISST-feedstock/hadisst.zarr"
    response = client.read_range(f"/repr/xarray/?url={url}")
    assert response["dataset"] == url
    assert response["html"]


def test_xarray_repr_errors(client):
    url = "https://mydataset.org/does-not-exist"

    response = client.read_range(f"/repr/xarray/?url={url}")
    assert (
        response["detail"]
        == f"An error occurred while fetching the data from URL: {url}. Dataset not found."
    )
