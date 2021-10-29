import json
import os
import re
from dataclasses import asdict
from typing import Optional

import fsspec
from pydantic.dataclasses import dataclass
from pydantic.networks import AnyUrl
import yaml
from fsspec.registry import get_filesystem_class

from .meta_types.bakery import (
    BakeryDatabase,
    BakeryMeta,
    BakeryName,
    BuildLogs,
    feedstock_name_with_version,
    KnownImplementations,
    StorageOptions,
    Target,
)


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
    default_prefix: Optional[str] = None
    default_fs: Optional[fsspec.AbstractFileSystem] = None
    build_logs: Optional[BuildLogs] = None

    private_storage_options: Optional[StorageOptions] = None
    private_protocol: Optional[KnownImplementations] = None
    private_prefix: Optional[str] = None
    credentialed_fs: Optional[fsspec.AbstractFileSystem] = None

    stac_relative_path: str = "stac"  # TODO: avoid repitition in __init__?

    def __init__(self, name, write_access=False, stac_relative_path="stac", **kwargs):
        super().__init__(**kwargs)

        self.name = BakeryName(name=name)
        self.metadata = BakeryMeta(**self.bakeries[self.name.name])
        self.write_access = write_access
        self.stac_relative_path = stac_relative_path

        targets = list(self.metadata.targets.keys())
        if len(targets) > 1:  # TODO: select target somehow
            raise NotImplementedError("This object doesn't support multiple Bakery targets.")
        self.target = asdict(self.metadata.targets[targets[0]])

        default_access = "public" if hasattr(self.target, "public") else "private"
        self.default_storage_options = getattr(self.target, default_access).storage_options
        self.default_protocol = getattr(self.target, default_access).protocol
        self.default_prefix = getattr(self.target, default_access).prefix

        default_fs_cls = get_filesystem_class(self.default_protocol)
        self.default_fs = default_fs_cls(**self.default_storage_options.dict(exclude_none=True))

        with self.default_fs.open(f"{self.get_base_path()}/build-logs.json") as f:
            build_logs_dict = json.loads(f.read())
            self.build_logs = BuildLogs(logs=build_logs_dict)

        if self.write_access:
            if not hasattr(self.target, "private"):
                raise ValueError("Write access requires target possess `private` attribute.")
            # assigning these values to `self` namespace calls type validation
            # (alternatively, validation could happen in `meta_types.bakery`)
            self.private_protocol = self.target.private.protocol
            self.private_storage_options = self.target.private.storage_options
            self.private_prefix = self.target.private.prefix
            private_fs_cls = get_filesystem_class(self.private_protocol)
            kw = self._recursively_replace_env_vars(
                self.private_storage_options.dict(exclude_none=True)
            )
            self.credentialed_fs = private_fs_cls(**kw)

    def _recursively_replace_env_vars(self, d):
        # this method is both (1) not a pure function (mutates instance attributes);
        # and (2) recursive. So it's perhaps more likely than other methods to create problems.
        # NB: We need recursion b/c `StorageOptions` can contain nested dicts of arbitary depth.
        # Let's keep an eye out, but I *think* it works as intendented.
        for k, v in d.items():
            if isinstance(v, dict):
                d[k] = self._recursively_replace_env_vars(v)  # noqa
            elif type(v) == str and v.startswith("{") and v.endswith("}"):
                v = self.remove_curly_braces(v)
                if v not in os.environ.keys():
                    raise KeyError(f"Environment variable {v} not set.")
                else:
                    d[k] = os.environ[v]
        return d

    @staticmethod
    def remove_curly_braces(v):
        return re.search("{(.*?)}", v).group(1).strip()

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


@dataclass
class FeedstockMetadata:

    feedstock_id: feedstock_name_with_version
    url_format: AnyUrl = "https://github.com/pangeo-forge/{name}/tree/v{majv}.{minv}"
    metadata_url_base: AnyUrl = "https://raw.githubusercontent.com"
    metadata_url_format: str = "pangeo-forge/{name}/v{majv}.{minv}/feedstock/meta.yaml"
    metadata_dict: Optional[dict] = None

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
