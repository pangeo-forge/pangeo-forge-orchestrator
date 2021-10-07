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
    target: str = field(init=False)
    root_path: str = field(init=False)
    kwargs: dict = field(init=False)

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
            self.target = self.bakery_dict[self.bakery_id]["targets"][k]
            self.root_path = self.target['root_path']
            self.kwargs = {k: v for k, v in self.target.items() if k != "root_path"}

            with fsspec.open(f"{self.root_path}/build-logs.json", **self.kwargs) as f2:
                read_json = f2.read()
                self.build_logs = json.loads(read_json)

    def filter_logs(self, feedstock):
        return {k: v for k, v in self.build_logs.items() if feedstock in v["feedstock"]}

    def get_mapper(self, run_id):
        ds_path = self.build_logs[run_id]["path"]
        full_path = f"{self.root_path}/{ds_path}"
        return fsspec.get_mapper(full_path, **self.kwargs)


@dataclass
class FeedstockMetadata:

    feedstock_id: str
    url_format: str = "https://github.com/pangeo-forge/{name}/tree/v{majv}.{minv}"
    metadata_url_format: str = (
        "https://raw.githubusercontent.com/pangeo-forge/{name}/v{majv}.{minv}/feedstock/meta.yaml"
    )
    metadata_dict: dict = field(init=False)

    def __post_init__(self):
        ids = self.feedstock_id.split("@")
        name, version = ids[0], ids[1]
        version_split = version.split(".")
        majv, minv = version_split[0], version_split[1]
        self.url = self.url_format.format(name=name, majv=majv, minv=minv)
        self.metadata_url = self.metadata_url_format.format(name=name, majv=majv, minv=minv)
        with fsspec.open(self.metadata_url) as f:
            read_yaml = f.read()
            self.metadata_dict = yaml.safe_load(read_yaml)
