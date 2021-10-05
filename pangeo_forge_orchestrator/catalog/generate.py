import xarray as xr
#import xstac

from ..utils import BakeryMetadata, FeedstockMetadata

#item_template =


def generate(bakery_id, run_id):
    """
    Generate a STAC Item for a Pangeo Forge Feedstock
    """
    bakery = BakeryMetadata(bakery_id=bakery_id)
    feedstock_id = bakery.build_logs[run_id]["feedstock"]
    fstock = FeedstockMetadata(feedstock_id=feedstock_id)

    mapper = bakery.get_mapper(run_id)
    ds = xr.open_zarr(mapper, consolidated=True)
    print(ds)
    
    #item = xstac.xarray_to_stac(ds, item_template)
    