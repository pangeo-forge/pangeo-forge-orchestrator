import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import re

import fsspec
import yaml
from fsspec.registry import get_filesystem_class, known_implementations

from .meta_types.bakery import BakeryDatabase, BakeryMeta, BakeryName, StorageOptions, Target

# turn fsspec's list of known_implementations into object which pydantic can validate against
KnownImplementations = Enum("KnownImplementations", [(p, p) for p in list(known_implementations)])


class Bakery(BakeryDatabase):
    """Bakery component of ``pangeo-forge-orchestrator``.

    :param id: The globally unique bakery name.
    :param metadata: Metadata about this bakery.
    :param write_access: Whether or not the instance grants write access to the bakery.
    :param target: The bakery target from with to read (and to which to write, if applicable).
    :param default_storage_options: Default access kwargs for the storage target. These are
        typically the ``public`` kwargs, but in cases where a target does not permit ``public``
        access, they may be ``private``.
    :param default_protocol: The protocol (e.g., http, s3, gcs, etc.) for default access.
    :param prefix: A string which precedes the dataset names at storage target.
    :param build_logs: Record of datasets built to the target.
    :param private_storage_options: Write access kwargs for target. Secrets are passed as
        environment variable names.
    :param private_protocol: The protocol used for write access to target.
    :param credentialed_fs: Credentialed fsspec filesystem for write access to target.
    """

    name: Optional[BakeryName] = None
    metadata: Optional[BakeryMeta] = None
    write_access: bool = False

    target: Optional[Target] = None
    default_storage_options: Optional[StorageOptions] = None
    default_protocol: Optional[KnownImplementations] = None
    prefix: Optional[str] = None
    build_logs: Optional[dict] = None  # TODO: define BuildLogs model

    private_storage_options: Optional[StorageOptions] = None
    private_protocol: Optional[KnownImplementations] = None
    credentialed_fs: Optional[fsspec.AbstractFileSystem] = None

    def __init__(self, name, write_access=False, **kwargs):
        super().__init__(**kwargs)

        self.name = BakeryName(name=name)
        self.metadata = BakeryMeta(**self.bakeries[self.name.name])
        self.write_access = write_access

        targets = list(self.metadata.targets.keys())
        if len(targets) > 1:  # TODO: select target somehow
            raise NotImplementedError("This object doesn't support multiple Bakery targets.")
        self.target = asdict(self.metadata.targets[targets[0]])

        default_access = "public" if hasattr(self.target, "public") else "private"
        self.default_storage_options = getattr(self.target, default_access).storage_options
        self.default_protocol = getattr(self.target, default_access).protocol
        self.prefix = getattr(self.target, default_access).prefix

        with fsspec.open(
            f"{self.get_base_path()}/build-logs.json",
            **self.default_storage_options.dict(exclude_none=True),
        ) as f:
            self.build_logs = json.loads(f.read())

        if self.write_access:
            if not hasattr(self.target, "private"):
                raise ValueError("Write access requires target possess `private` attribute.")
            # assigning these values to `self` namespace calls type validation
            # (alternatively, validation could happen in `meta_types.bakery`)
            self.private_protocol = self.target.private.protocol
            self.private_storage_options = self.target.private.storage_options
            fs_cls = get_filesystem_class(self.private_protocol.name)
            env_vars = [
                v for v in self.private_storage_options.values()
                if type(v) == str and v.startswith("{") and v.endswith("}")
            ]
            for v in env_vars:
                if self.remove_curly_braces(v) not in os.environ.keys():
                    raise ValueError(f"Environment variable {self.remove_curly_braces(v)} not set.")
            kw = {
                k: (v if v not in env_vars else os.environ[self.remove_curly_braces(v)])
                for k, v in self.private_storage_options.items()
            }
            self.credentialed_fs = fs_cls(**kw)

    @staticmethod
    def remove_curly_braces(v):
        return re.search("{(.*?)}", v).group(1).strip()

    def filter_logs(self, feedstock):
        return {k: v for k, v in self.build_logs.items() if feedstock in v["feedstock"]}

    def get_base_path(self):
        return f"{self.default_protocol.name}://{self.prefix}"

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
