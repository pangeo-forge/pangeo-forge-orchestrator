import json
from dataclasses import asdict
from pathlib import Path

import shapely.geometry
import xarray as xr
import xstac
from rich import print

from .interfaces import Bakery, Feedstock


def generate(
    bakery_name,
    run_id,
    bakery_database_path=None,
    bakery_stac_relative_path=None,
    feedstock_metadata_url_base=None,
    print_result=False,
    to_file=False,
    endpoints=["s3", "https"],
):
    write_access = True if to_file else False
    item_result, feedstock_id, bakery = _generate(
        bakery_name=bakery_name,
        run_id=run_id,
        bakery_database_path=bakery_database_path,
        bakery_stac_relative_path=bakery_stac_relative_path,
        feedstock_metadata_url_base=feedstock_metadata_url_base,
        endpoints=endpoints,
        write_access=write_access,
    )
    if print_result:
        print(item_result)
    if not to_file:
        return item_result
    elif to_file:
        stac_item_filename = f"{feedstock_id}.json"
        with open(stac_item_filename, mode="w") as outfile:
            json.dump(item_result, outfile)
        # if to_bakery:
        item_dst_path = f"{bakery.get_stac_path(write_access=True)}{stac_item_filename}"
        bakery.put(stac_item_filename, item_dst_path)

        return item_result


def _generate(
    bakery_name,
    run_id,
    bakery_database_path,
    bakery_stac_relative_path,
    feedstock_metadata_url_base,
    endpoints,
    write_access,
):
    """
    Generate a STAC Item for a Pangeo Forge Feedstock
    """
    parent = Path(__file__).absolute().parent
    with open(f"{parent}/templates/stac/item_template.json") as f:
        item_template = json.loads(f.read())

    bakery_kw = dict(name=bakery_name, write_access=write_access)
    if bakery_database_path:
        bakery_kw.update(dict(database_path=bakery_database_path))
    if bakery_stac_relative_path != None:  # noqa; empty strings don't eval w/ `cond is not None`
        bakery_kw.update(dict(stac_relative_path=bakery_stac_relative_path))
    bakery = Bakery(**bakery_kw)

    feedstock_id = bakery.build_logs.logs[run_id].feedstock
    fstock_kw = dict(feedstock_id=feedstock_id)
    if feedstock_metadata_url_base:
        fstock_kw.update(dict(metadata_url_base=feedstock_metadata_url_base))
    fstock = Feedstock(**fstock_kw)

    mapper = bakery.get_dataset_mapper(run_id)
    ds = xr.open_zarr(mapper, consolidated=True)
    bbox = _make_bounding_box(ds)
    time_bounds = _make_time_bounds(ds)

    # -------------- TOP LEVEL FIELDS + PROPERTIES ---------------
    item_template["id"] = feedstock_id
    item_template["bbox"] = bbox
    item_template["geometry"] = shapely.geometry.mapping(shapely.geometry.box(*bbox))
    for k in time_bounds.keys():
        item_template["properties"][k] = time_bounds[k]

    # ---------------------- ASSETS ------------------------------
    assets = item_template["assets"]
    # ~~~~~~~~~~~~~~~~~~~~ Data Assets ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    for ep in endpoints:
        key = f"zarr-{ep}"
        assets.update(
            {
                f"{key}": {
                    "href": "",
                    "type": "application/vnd+zarr",
                    "title": "",
                    "description": "",
                    "roles": ["data", "zarr", f"{ep}"],
                    "xarray:storage_options": None,
                    "xarray:open_kwargs": None,
                },
            }
        )
        longname = f"{ep.upper()} File System"
        path = bakery.get_dataset_path(run_id)
        assets[key]["href"] = path
        assets[key]["title"] = f"{fstock.meta_dot_yaml.title} - {longname} Zarr root"
        desc = fstock.meta_dot_yaml.description
        desc = f"{desc[0].lower()}{desc[1:]}"
        # all descriptions may not work with this format string; generalize more, perhaps.
        assets[key]["description"] = f"{longname} Zarr root for {desc}"
        # add `xarray assets` extension details
        assets[key]["xarray:open_kwargs"] = dict(consolidated=True)
        if ep == "s3":
            assets[key]["xarray:storage_options"] = bakery.default_storage_options.dict(
                exclude_none=True
            )

    # ~~~~~~~~~~~~~~~~~~~~ Feedstock Asset ~~~~~~~~~~~~~~~~~~~~~~~
    pff = "pangeo-forge-feedstock"
    assets[pff]["href"] = fstock.url
    assets[pff]["title"] = f"Pangeo Forge Feedstock (GitHub repository) for {feedstock_id}"

    # ~~~~~~~~~~~~~~~~~~~~ Notebook Assets ~~~~~~~~~~~~~~~~~~~~~~~
    # Added in `generate` function. Requires `item_result` dict as input.

    # ~~~~~~~~~~~~~~~~~~~~ Thumbnail Asset ~~~~~~~~~~~~~~~~~~~~~~~
    # how are we going to create thumbnails? link them from `meta.yaml`?
    if "thumbnails" not in asdict(fstock.meta_dot_yaml).keys():
        del assets["thumbnail"]

    # ---------------------- XSTAC -------------------------------
    # to generalize this, contributors may need to specify dimensions + ref system in `meta.yaml`?
    kw = dict(
        temporal_dimension="time", x_dimension="lon", y_dimension="lat", reference_system=False
    )
    item = xstac.xarray_to_stac(ds, item_template, **kw)
    item_result = item.to_dict(include_self_link=False)
    return item_result, feedstock_id, bakery


def _make_bounding_box(ds):
    """
    Create a STAC-compliant bounding box from an xarray dataset.
    """
    # generalizable if cf convention linting is implemented in recipe contribution workflow?
    # https://cfconventions.org/Data/cf-conventions/cf-conventions-1.9/cf-conventions.html#latitude-coordinate
    lats = [ds["lat"].values[0], ds["lat"].values[-1]]
    lons = [ds["lon"].values[0], ds["lon"].values[-1]]
    # convert longitude from 0-360 scale to -180-180 scale
    lons = [lon - 360 if lon > 180 else lon for lon in lons]
    lons = sorted(lons)
    # rearrange values into specified format: [min lon, min lat, max lon, max lat]
    # https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#bbox
    # (STAC also doesn't accept `numpy.float64` so recast to builtin `float`)
    return [float(dim[i]) for dim in zip(lons, lats) for i in range(2)]


def _make_time_bounds(ds):
    """
    Create STAC-compliant time bounds from an xarray dataset.
    """
    # datetime handling will require edge-casing for model output data, etc.
    def format_datetime(n, ds=ds):
        return f"{str(ds['time'].values[n])[:19]}Z"

    time_bounds = (
        {b: format_datetime(n) for n, b in zip([0, -1], ["start_datetime", "end_datetime"])}
        if len(ds["time"]) > 1
        else {"datetime": format_datetime(n=0)}
    )
    return time_bounds
