import os

import yaml
from dacite import from_dict

from pangeo_forge_prefect.meta_types.bakery import Bakery
from pangeo_forge_prefect.meta_types.meta import Meta

with open(f"{os.path.dirname(__file__)}/bakeries.yaml") as bakeries_yaml:
    bakeries_dict = yaml.load(bakeries_yaml, Loader=yaml.FullLoader)
    bakery = from_dict(
        data_class=Bakery,
        data=bakeries_dict["devseed.bakery.development.aws.us-west-2"],
    )

with open(f"{os.path.dirname(__file__)}/meta.yaml") as meta_yaml:
    meta_dict = yaml.load(meta_yaml, Loader=yaml.FullLoader)
    meta = from_dict(data_class=Meta, data=meta_dict)
