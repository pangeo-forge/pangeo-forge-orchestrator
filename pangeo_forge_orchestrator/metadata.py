import ast
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

import fsspec
import yaml
from pydantic import AnyUrl, BaseModel, FilePath
from fsspec.registry import get_filesystem_class, known_implementations

PANGEO_FORGE_BAKERY_DATABASE = (
    "https://raw.githubusercontent.com/pangeo-forge/bakery-database/main/bakeries.yaml"
)
# turn fsspec's list of known_implementations into object which pydantic can validate against
KnownImplementations = Enum("KnownImplementations", [(p, p) for p in list(known_implementations)])


class BakeryDatabase(BaseModel):
    """The place
    """

    path: Optional[Union[AnyUrl, FilePath]] = None  # Not optional, but assigned in __init__
    bakeries: Optional[dict] = None  # TODO: Custom type for `bakeries`

    class Config:
        validate_assignment = True  # validate `__init__` assignments
        arbitrary_types_allowed = True

    def __init__(self, path=PANGEO_FORGE_BAKERY_DATABASE):
        super().__init__()
        self.path = path
        with fsspec.open(self.path) as f:
            self.bakeries = yaml.safe_load(f.read())


class BakeryMetadata(BakeryDatabase):

    id: Optional[str] = None  # Not optional, but assigned in __init__
    build_logs: Optional[dict] = None
    target: Optional[dict] = None
    root: Optional[str] = None
    protocol: Optional[KnownImplementations] = None
    fsspec_open_kwargs: Optional[dict] = None
    write_access: bool = False
    credentialed_fs: Optional[fsspec.AbstractFileSystem] = None

    def __init__(self, id, write_access=False, **kwargs):
        super().__init__(**kwargs)
        self.id = id
        self.write_access = write_access
        targets = list(self.bakeries[self.id]["targets"].keys())
        if len(targets) > 1:
            raise NotImplementedError("This object doesn't support multiple Bakery targets.")
        self.target = self.bakeries[self.id]["targets"][targets[0]]
        self.protocol = self.target["private"]["protocol"]
        self.read_only_kwargs = self.target["private"]["storage_options"]

        with fsspec.open(
            f"{self.protocol.name}://{self.root}/build-logs.json", **self.read_only_kwargs,
        ) as f:
            self.build_logs = json.loads(f.read())

        if self.write_access:
            fs_cls = get_filesystem_class(self.protocol.name)
            if "PANGEO_FORGE_BAKERY_WRITE_KWARGS" not in os.environ.keys():
                raise ValueError(
                    "Environment variable 'PANGEO_FORGE_BAKERY_WRITE_KWARGS' is not set. This "
                    "variable is the string representation of the kwarg dictionary required to "
                    "instantiate a credentialed fsspec filesystem for this Bakery. To set this "
                    "variable, define your kwargs as a Python `dict` named `kwargs` and then call "
                    "`os.environ['PANGEO_FORGE_BAKERY_WRITE_KWARGS'] = str(kwargs)`. These kwargs "
                    "will contain secrets; **do not** commit them to version control."
                )
            kw = ast.literal_eval(os.environ["PANGEO_FORGE_BAKERY_WRITE_KWARGS"])
            self.credentialed_fs = fs_cls(**kw)

    def filter_logs(self, feedstock):
        return {k: v for k, v in self.build_logs.items() if feedstock in v["feedstock"]}

    def get_base_path(self, endpoint):
        prefixes = {  # not generalizable beyond OSN
            "s3": "s3://",
            "https": f"{self.fsspec_open_kwargs['client_kwargs']['endpoint_url']}/"
        }
        return f"{prefixes[endpoint]}{self.root}"

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
