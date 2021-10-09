import json
import os
from dataclasses import dataclass, field
from typing import Optional

import fsspec
import s3fs
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
    bakery_root: str = field(init=False)
    fsspec_open_kwargs: dict = field(init=False)
    write_access: bool = False
    credentialed_fs: Optional[s3fs.S3FileSystem] = None

    def __post_init__(self):
        with fsspec.open(self.bakery_database) as f:
            read_yaml = f.read()
            self.bakery_dict = yaml.safe_load(read_yaml)

            # add an additional mock bakery for testing purposes
            osn = dict(
                fsspec_open_kwargs=dict(
                    anon=True,
                    client_kwargs={'endpoint_url': 'https://ncsa.osn.xsede.org'},
                ),
                protocol="s3",
                bakery_root="Pangeo/pangeo-forge",
            )
            self.bakery_dict.update({"great_bakery": {"targets": {"osn": osn}}})

        if self.bakery_id:
            k = list(self.bakery_dict[self.bakery_id]["targets"].keys())[0]
            self.target = self.bakery_dict[self.bakery_id]["targets"][k]
            self.bakery_root = self.target["bakery_root"]
            self.fsspec_open_kwargs = self.target["fsspec_open_kwargs"]

            with fsspec.open(
                f"{self.target['protocol']}://{self.bakery_root}/build-logs.json",
                **self.fsspec_open_kwargs,
            ) as f2:
                self.build_logs = json.loads(f2.read())

            if self.write_access:
                # this, of course, is S3/OSN specific
                for k in ["OSN_KEY", "OSN_SECRET"]:
                    if k not in os.environ.keys():
                        raise ValueError(
                            f"Environment variable {k} required to authenticate write access."
                        )
                self.credentialed_fs = s3fs.S3FileSystem(
                    key=os.environ["OSN_KEY"],
                    secret=os.environ["OSN_SECRET"],
                    client_kwargs=self.fsspec_open_kwargs["client_kwargs"],
                    default_cache_type='none',
                    default_fill_cache=False,
                    use_listings_cache=False
                )

    def filter_logs(self, feedstock):
        return {k: v for k, v in self.build_logs.items() if feedstock in v["feedstock"]}

    def get_base_path(self, endpoint):
        prefixes = {  # not generalizable beyond OSN
            "s3": "s3://",
            "https": f"{self.fsspec_open_kwargs['client_kwargs']['endpoint_url']}/"
        }
        return f"{prefixes[endpoint]}{self.bakery_root}"

    def get_dataset_path(self, run_id, endpoint="s3"):
        ds_path = self.build_logs[run_id]["path"]
        return f"{self.get_base_path(endpoint)}/{ds_path}"

    def get_dataset_mapper(self, run_id):
        path = self.get_dataset_path(run_id)
        return fsspec.get_mapper(path, **self.fsspec_open_kwargs)

    def upload_stac_item(self, stac_item_filename):
        bucket = self.get_base_path("s3")
        item_bakery_path = f"{bucket}/stac/{stac_item_filename}"
        self.credentialed_fs.put(stac_item_filename, item_bakery_path)
        item_bakery_http_path = item_bakery_path.replace(bucket, self.get_base_path("https"))
        return item_bakery_http_path


@dataclass
class FeedstockMetadata:

    feedstock_id: str
    url_format: str = "https://github.com/pangeo-forge/{name}/tree/v{majv}.{minv}"
    metadata_url_format: str = (
        "https://raw.githubusercontent.com/pangeo-forge/{name}/v{majv}.{minv}/feedstock/meta.yaml"
    )
    metadata_dict: dict = field(init=False)
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
