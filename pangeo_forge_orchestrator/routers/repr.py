import pydantic
from fastapi import APIRouter, JSONResponse, Query, status

repr_router = APIRouter()


@repr_router.get("/xarray/", summary="Get xarray representation of dataset", tags=["repr"])
def xarray(
    url: pydantic.AnyUrl = Query(
        ...,
        description="URL to a zarr store",
        example="https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/HadISST-feedstock/hadisst.zarr",
    )
):

    import xarray as xr
    import zarr

    error_message = f"An error occurred while fetching the data from URL: {url}"

    try:

        with xr.open_dataset(url, engine="zarr", chunks={}) as ds:
            html = ds._repr_html_().strip()

        del ds

        return {"html": html, "dataset": url}

    except (zarr.errors.GroupNotFoundError, FileNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"{error_message}. Dataset not found."},
        )

    except PermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": f"{error_message}. Permission denied."},
        )
