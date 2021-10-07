import json

from rich import print
import shapely.geometry
import xarray as xr
import xstac

from ..utils import BakeryMetadata, FeedstockMetadata

with open("item_template.json") as f:
    item_template = json.loads(f.read())

def generate(bakery_id, run_id):
    """
    Generate a STAC Item for a Pangeo Forge Feedstock
    """
    bakery = BakeryMetadata(bakery_id=bakery_id)
    feedstock_id = bakery.build_logs[run_id]["feedstock"]
    fstock = FeedstockMetadata(feedstock_id=feedstock_id)

    mapper = bakery.get_mapper(run_id)
    ds = xr.open_zarr(mapper, consolidated=True)

    # dim names generalizable if cf convention linting is implemented in recipe contribution workflow?
    # https://cfconventions.org/Data/cf-conventions/cf-conventions-1.9/cf-conventions.html#latitude-coordinate
    lats = [ds["lat"].values[0], ds["lat"].values[-1]]
    lons = [ds["lon"].values[0], ds["lon"].values[-1]]
    # convert longitude from 0-360 scale to -180-180 scale
    lons = [lon - 360 if lon > 180 else lon for lon in lons]
    lons = sorted(lons)
    # rearrange values into specified format: [min lon, min lat, max lon, max lat]
    # https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#bbox
    # (STAC also doesn't accept `numpy.float64` so recast to builtin `float`)
    bbox = [float(dim[i]) for dim in zip(lons, lats) for i in range(2)]

    # -------------- TOP LEVEL FIELDS + PROPERTIES ---------------
    item_template["id"] = fstock.feedstock_id
    item_template["bbox"] = bbox
    item_template["geometry"] = shapely.geometry.mapping(shapely.geometry.box(*bbox))
    # datetime handling will require edge-casing for model output data, etc.
    if len(ds['time']) > 1:
        for n, timebound in zip([0, -1], ["start_datetime", "end_datetime"]):
            item_template["properties"][timebound] = f"{str(ds['time'].values[n])[:19]}Z"
    else:
        item_template["properties"][datetime] = f"{str(ds['time'].values[0])[:19]}Z"

    # ---------------------- ASSETS ------------------------------
    assets = item_template["assets"]
    for endpoint in ["zarr-s3", "zarr-https"]:
        longname = "S3 File System" if endpoint == "zarr-s3" else "HTTPS"
        path = f"{bakery.root_path}/{bakery.build_logs[run_id]['path']}"
        # probably want to move http endpoint info into the BakeryMetadata dataclass eventually
        path = (
            path
            if endpoint == "zarr-s3"
            else path.replace("s3://", "https://ncsa.osn.xsede.org/")
        )
        assets[endpoint]["href"] = path
        assets[endpoint]["title"] = f"{fstock.metadata_dict['title']} - {longname} Zarr root"
        desc = fstock.metadata_dict['description']
        desc = f"{desc[0].lower()}{desc[1:]}"
        # all descriptions may not work with this format string; generalize more, perhaps.
        assets[endpoint]["description"] = f"{longname} Zarr root for {desc}"

    assets["pangeo-forge-feedstock"]["href"] = fstock.url
    assets["jupyter-notebook-example"]["href"] = "URL" # CHANGE THIS
    # how are we going to create thumbnails? link them from `meta.yaml`?
    if "thumbnails" not in fstock.metadata_dict.keys():
        del assets["thumbnail"]

    # ---------------------- XSTAC _------------------------------
    # to generalize this, contributors may need to specify dimensions + ref system in `meta.yaml`?
    kw = dict(temporal_dimension="time", x_dimension="lon", y_dimension="lat", reference_system=False)
    item = xstac.xarray_to_stac(ds, item_template, **kw)
    item_result = item.to_dict(include_self_link=False)

    print(item_result)
