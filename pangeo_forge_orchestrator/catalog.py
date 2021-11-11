import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import cf_xarray  # noqa
import shapely.geometry
import xarray as xr
import xstac
from rich import print

from .interfaces import Bakery, Feedstock

xr.set_options(keep_attrs=True)  # for cf_xarray

fmt_openers = dict(zarr=xr.open_zarr)
fmt_kwargs = dict(zarr=dict(consolidated=True))


def generate(
    bakery_name: str,
    run_id: int,
    bakery_database_path: Optional[str] = None,
    bakery_stac_relative_path: Optional[str] = None,
    feedstock_metadata_url_base: Optional[str] = None,
    print_result: bool = False,
    to_file: bool = False,
) -> None:
    """Generate a STAC Item for a Pangeo Forge ARCO dataset.

    :param bakery_name: [description]
    :param run_id: [description]
    :param bakery_database_path: [description]. Defaults to None.
    :param bakery_stac_relative_path: [description]. Defaults to None.
    :param feedstock_metadata_url_base: [description]. Defaults to None.
    :param print_result: [description]. Defaults to False.
    :param to_file: [description]. Defaults to False.
    :param endpoints: [description]. Defaults to ["s3", "https"].

    Returns:
        None: [description]
    """
    item_result, feedstock_id, bakery = _make_stac_item(
        bakery_name=bakery_name,
        run_id=run_id,
        bakery_database_path=bakery_database_path,
        bakery_stac_relative_path=bakery_stac_relative_path,
        feedstock_metadata_url_base=feedstock_metadata_url_base,
        write_access=to_file,
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
        item_dst_path = (
            f"{bakery.get_asset_path(asset='stac', access='private')}{stac_item_filename}"
        )
        bakery.put(stac_item_filename, item_dst_path)

        return item_result


def _make_stac_item(
    bakery_name,
    run_id,
    bakery_database_path,
    bakery_stac_relative_path,
    feedstock_metadata_url_base,
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
    fmt = mapper.root.split(".")[-1]
    ds_opener, ds_open_kwargs = fmt_openers[fmt], fmt_kwargs[fmt]
    ds = ds_opener(mapper, **ds_open_kwargs)

    # -------------- Infer axes with `cf_xarray` -----------------
    ds = ds.cf.guess_coord_axis()  # pass `verbose=True` for debugging
    # TODO: Upstream following loop to `cf_xarray.accessor::ATTRS` dict?
    for ax, coord in zip(("X", "Y"), ("longitude", "latitude")):
        if ax not in ds.cf.axes.keys() and coord in ds.cf.coordinates.keys():
            for c in ds.cf.coordinates[coord]:
                ds[c].attrs.update(dict(axis=ax))
    dims = dict(
        temporal_dimension=("T" if "T" in ds.cf.axes.keys() else None),
        x_dimension=("X" if "X" in ds.cf.axes.keys() else None),
        y_dimension=("Y" if "Y" in ds.cf.axes.keys() else None),
    )

    # -------------- TOP LEVEL FIELDS + PROPERTIES ---------------
    # If any of these are missing, we won't have a valid STAC Item
    # TODO: Resolve redundancy with `xstac`/datacube extension section below.
    if dims["temporal_dimension"] is not None:
        time_bounds = _make_time_bounds(ds)
        for k in time_bounds.keys():
            item_template["properties"][k] = time_bounds[k]
    if dims["x_dimension"] is not None and dims["y_dimension"] is not None:
        bbox = _make_bounding_box(ds)
        item_template["id"] = feedstock_id
        item_template["bbox"] = bbox
        item_template["geometry"] = shapely.geometry.mapping(shapely.geometry.box(*bbox))

    # ---------------------- ASSETS ------------------------------
    assets = item_template["assets"]
    # ~~~~~~~~~~~~~~~~~~~~ Data Assets ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # TODO: What if there is more than one public endpoint? e.g., http + s3
    # └──> (Bakery database spec doesn't seem to support this currently; only "public vs. private".)
    # The following is a loop to leave room for this in the future.
    for access in ["default"]:
        protocol = getattr(bakery, f"{access}_protocol")
        key = f"zarr-{protocol}"
        assets.update(
            {
                f"{key}": {
                    "href": "",
                    "type": "application/vnd+zarr",
                    "title": "",
                    "description": "",
                    "roles": ["data", "zarr", f"{protocol}"],
                    "xarray:storage_options": None,
                    "xarray:open_kwargs": None,
                },
            }
        )
        longname = f"{protocol.upper()} File System"
        path = bakery.get_dataset_path(run_id, access=access)
        assets[key]["href"] = path
        assets[key]["title"] = f"{fstock.meta_dot_yaml.title} - {longname} Zarr root"
        desc = fstock.meta_dot_yaml.description
        desc = f"{desc[0].lower()}{desc[1:]}"
        # TODO: all descriptions may not work with this format string; generalize more, perhaps.
        assets[key]["description"] = f"{longname} Zarr root for {desc}"
        # add `xarray assets` extension details
        assets[key]["xarray:open_kwargs"] = ds_open_kwargs
        so = getattr(bakery, f"{access}_storage_options")
        assets[key]["xarray:storage_options"] = so.dict(exclude_none=True)

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
    if None not in dims.values():
        # we have all necessary dimension names; generate Datacube Extension via `xstac`
        item = xstac.xarray_to_stac(
            ds, item_template, via_cf_namespace=True, reference_system=False, **dims
        )
        item_result = item.to_dict(include_self_link=False)
    else:
        # missing at least one required dim name; skip Datacube Extension generation
        item_result = item_template

    return item_result, feedstock_id, bakery


def _make_bounding_box(ds):
    """
    Create a STAC-compliant bounding box from an xarray dataset.
    """
    # generalizable if cf convention linting is implemented in recipe contribution workflow?
    # https://cfconventions.org/Data/cf-conventions/cf-conventions-1.9/cf-conventions.html#latitude-coordinate
    lats = [ds.cf["Y"].values[0], ds.cf["Y"].values[-1]]
    lons = [ds.cf["X"].values[0], ds.cf["X"].values[-1]]
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
        return f"{str(ds.cf['T'].values[n])[:19]}Z"

    time_bounds = (
        {b: format_datetime(n) for n, b in zip([0, -1], ["start_datetime", "end_datetime"])}
        if len(ds.cf["T"]) > 1
        else {"datetime": format_datetime(n=0)}
    )
    return time_bounds
