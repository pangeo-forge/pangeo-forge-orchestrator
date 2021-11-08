import copy
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Optional

import fsspec
import yaml  # type: ignore
from fsspec.registry import get_filesystem_class
from pydantic.dataclasses import dataclass as pydantic_dataclass

from .meta_types.bakery import (
    BakeryMeta,
    BakeryName,
    BuildLogs,
    KnownImplementations,
    StorageOptions,
    Target,
    bakery_database_from_dict,
    feedstock_name_with_version,
)

PANGEO_FORGE_BAKERY_DATABASE = (
    "https://raw.githubusercontent.com/pangeo-forge/bakery-database/main/bakeries.yaml"
)


@dataclass
class Bakery:
    """Bakery component of ``pangeo-forge-orchestrator``.

    :param name: The globally unique bakery name.
    :param write_access: Whether or not the instance grants write access to the bakery.
    :param stac_relative_path: The relative path within the bakery where STAC Items are stored.
    :param database_path: Path to a bakery database file containing metadata about the bakery.
    """

    name: str
    write_access: bool = False
    stac_relative_path: str = "stac"
    database_path: str = PANGEO_FORGE_BAKERY_DATABASE

    def __post_init__(self):

        with fsspec.open(self.database_path) as f:
            d = yaml.safe_load(f.read())
            self.bakery_database = bakery_database_from_dict(d)

        with self.default_fs.open(f"{self.get_base_path()}/build-logs.json") as f:
            build_logs_dict = json.load(f)
            self.build_logs = BuildLogs(logs=build_logs_dict)

        if self.write_access:
            if not hasattr(self.target, "private"):
                raise ValueError("Write access requires target possess `private` attribute.")
            # ensure that all env vars are assigned
            _ = _recursively_replace_env_vars(self.private_storage_options.dict(exclude_none=True))

    @property
    def bakery_name(self) -> BakeryName:
        return BakeryName(self.name)

    @property
    def metadata(self) -> BakeryMeta:
        return self.bakery_database.bakeries[self.bakery_name]

    @property
    def target(self) -> Target:
        targets = list(self.metadata.targets.keys())
        if len(targets) > 1:  # TODO: select target somehow
            raise NotImplementedError("This object doesn't support multiple Bakery targets.")
        return Target(**asdict(self.metadata.targets[targets[0]]))

    @property
    def default_access(self) -> str:
        return "public" if hasattr(self.target, "public") else "private"

    @property
    def default_storage_options(self) -> StorageOptions:
        return getattr(self.target, self.default_access).storage_options

    @property
    def default_protocol(self) -> KnownImplementations:  # type: ignore
        return getattr(self.target, self.default_access).protocol

    @property
    def default_prefix(self) -> str:
        return getattr(self.target, self.default_access).prefix

    @property
    def default_fs(self) -> fsspec.AbstractFileSystem:
        cls = get_filesystem_class(self.default_protocol)
        return cls(**self.default_storage_options.dict(exclude_none=True))

    @property
    def private_protocol(self) -> KnownImplementations:  # type: ignore
        return self.target.private.protocol  # type: ignore

    @property
    def private_storage_options(self) -> Optional[StorageOptions]:
        return self.target.private.storage_options  # type: ignore

    @property
    def private_prefix(self) -> Optional[str]:
        return self.target.private.prefix  # type: ignore

    @property
    def credentialed_fs(self) -> fsspec.AbstractFileSystem:
        cls = get_filesystem_class(self.private_protocol)
        kw = _recursively_replace_env_vars(
            self.private_storage_options.dict(exclude_none=True)  # type: ignore
        )
        return cls(**kw)

    def filter_logs(self, feedstock):
        return {k: v for k, v in self.build_logs.logs.items() if feedstock in v.feedstock}

    def get_base_path(self, write_access=False):
        protocol = self.default_protocol if not write_access else self.private_protocol
        prefix = self.default_prefix if not write_access else self.private_prefix
        return f"{protocol}://{prefix}"

    def get_stac_path(self, write_access=False):
        return f"{self.get_base_path(write_access=write_access)}/{self.stac_relative_path}"

    def get_dataset_path(self, run_id):
        ds_path = self.build_logs.logs[run_id].path
        return f"{self.get_base_path()}/{ds_path}"

    def get_dataset_mapper(self, run_id):
        path = self.get_dataset_path(run_id)
        return fsspec.get_mapper(path, **self.default_storage_options.dict(exclude_none=True))

    def cat(self, path):
        return self.default_fs.cat(path)

    def put(self, src_path, dst_path, **kwargs):
        if "http" in dst_path:
            # needed for testing, but don't think this hurts?
            # in reality, we'll rarely be writing over http(s)
            cl = os.path.getsize(src_path)
            headers = {"Content-Length": str(cl)}
            kwargs.update(dict(headers=headers))
        self.credentialed_fs.put(src_path, dst_path, **kwargs)


@pydantic_dataclass
class FeedstockMetadata:

    feedstock_id: feedstock_name_with_version  # type: ignore
    url_format: str = "https://github.com/pangeo-forge/{name}/tree/v{majv}.{minv}"
    metadata_url_base: str = "https://raw.githubusercontent.com"
    metadata_url_format: str = "pangeo-forge/{name}/v{majv}.{minv}/feedstock/meta.yaml"

    def __post_init_post_parse__(self):
        # We are using `__post_init_post_parse__`, as opposed to `__post_init__`, so that we can
        # validate `self.feedstock_id` before doing the remainder of our field assignements, below.
        ids = self.feedstock_id.split("@")
        name, version = ids[0], ids[1]
        version_split = version.split(".")
        majv, minv = version_split[0], version_split[1]
        self.url = self.url_format.format(name=name, majv=majv, minv=minv)

        self.metadata_url = (
            f"{self.metadata_url_base}/"
            f"{self.metadata_url_format.format(name=name, majv=majv, minv=minv)}"
        )
        with fsspec.open(self.metadata_url) as f:
            read_yaml = f.read()
            self.metadata_dict = yaml.safe_load(read_yaml)


def _remove_curly_braces(v):
    return re.search("{(.*?)}", v).group(1).strip()


def _recursively_replace_env_vars(d):
    # NB: We need recursion b/c `StorageOptions` can contain nested dicts of arbitary depth.
    d = copy.deepcopy(d)
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = _recursively_replace_env_vars(v)  # noqa
        elif type(v) == str and v.startswith("{") and v.endswith("}"):
            v = _remove_curly_braces(v)
            if v not in os.environ.keys():
                raise KeyError(f"Environment variable {v} not set.")
            else:
                d[k] = os.environ[v]
    return d
