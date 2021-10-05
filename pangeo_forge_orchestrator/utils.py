import json
from dataclasses import dataclass, field
from typing import Optional

import fsspec
import yaml


@dataclass
class BakeryMetadata:

    bakery_database: str = (
        "https://raw.githubusercontent.com/pangeo-forge/bakery-database/main/bakeries.yaml"
    )
    bakery_dict: dict = field(init=False)
    bakery_id: Optional[str] = None
    build_logs: dict = field(default_factory=dict)

    def __post_init__(self):
        with fsspec.open(self.bakery_database) as f:
            read_yaml = f.read()
            self.bakery_dict = yaml.safe_load(read_yaml)

            # add an additional mock bakery for testing purposes
            osn = dict(
                anon=True,
                client_kwargs={'endpoint_url': 'https://ncsa.osn.xsede.org'},
                root_path="s3://Pangeo/pangeo-forge",
            )
            self.bakery_dict.update({"great_bakery": {"targets": {"osn": osn}}})

        if self.bakery_id:
            k = list(self.bakery_dict[self.bakery_id]["targets"].keys())[0]
            target = self.bakery_dict[self.bakery_id]["targets"][k]
            kwargs = {k: v for k, v in target.items() if k != "root_path"}

            with fsspec.open(f"{target['root_path']}/build-logs.json", **kwargs) as f2:
                read_json = f2.read()
                self.build_logs = json.loads(read_json)
