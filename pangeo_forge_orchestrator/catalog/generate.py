from rich import print
import shapely.geometry
import xarray as xr
import xstac

from ..utils import BakeryMetadata, FeedstockMetadata


BBOX = [-160.3056, 17.9539, -154.772, 23.5186]

item_template = {
    "id": "ID",  # f"daymet-{frequency}-{region}",
    "type": "Feature",
    "links": [],
    "bbox": BBOX,
    "geometry": shapely.geometry.mapping(shapely.geometry.box(*BBOX)),
    "stac_version": "1.0.0",
    "properties": {
        "datetime": "2021-01-01T00:00:00Z"
    },
    "assets": {
        "zarr-https": {
            "href": "HREF", # f"https://daymeteuwest.blob.core.windows.net/daymet-zarr/{frequency}/{region}.zarr",
            "type": "application/vnd+zarr",
#            "title": f"{frequency.title()} {FULL_REGIONS[region]} Daymet HTTPS Zarr root",
#            "description": f"HTTPS URI of the {frequency} {FULL_REGIONS[region]} Daymet Zarr Group on Azure Blob Storage.",
            "roles": ["data", "zarr", "https"],
        },
        "zarr-abfs": {
            "href": "HREF", # f"abfs://daymet-zarr/{frequency}/{region}.zarr",
            "type": "application/vnd+zarr",
#            "title": f"{frequency.title()} {FULL_REGIONS[region]} Daymet Azure Blob File System Zarr root",
#            "description": f"Azure Blob File System of the {frequency} {FULL_REGIONS[region]} Daymet Zarr Group on Azure Blob Storage for use with adlfs.",
            "roles": ["data", "zarr", "abfs"],
        },
        "thumbnail": {
            "href": "HREF", # f"https://ai4edatasetspublicassets.blob.core.windows.net/assets/pc_thumbnails/daymet-{frequency}-{region}.png",
            "type": "image/png",
#            "title": f"Daymet {frequency} {FULL_REGIONS[region]} map thumbnail",
        },
    },
}

def generate(bakery_id, run_id):
    """
    Generate a STAC Item for a Pangeo Forge Feedstock
    """
    bakery = BakeryMetadata(bakery_id=bakery_id)
    feedstock_id = bakery.build_logs[run_id]["feedstock"]
    fstock = FeedstockMetadata(feedstock_id=feedstock_id)

    mapper = bakery.get_mapper(run_id)
    ds = xr.open_zarr(mapper, consolidated=True)

    item = xstac.xarray_to_stac(ds, item_template)
    item_result = item.to_dict(include_self_link=False)

    print(item_result)
    