import ast
import json
import os

import fsspec
import pytest
import xarray as xr
from aiohttp.client_exceptions import ClientResponseError
from fsspec.implementations.http import HTTPFileSystem
from pydantic import ValidationError

from pangeo_forge_orchestrator.components import Bakery, FeedstockMetadata
from pangeo_forge_orchestrator.meta_types.bakery import BakeryMeta, BakeryName

from .test_server import write_test_file


@pytest.mark.parametrize("invalid", [None, "database_path", "bakery_name"])
def test_bakery_component_read_only(invalid, github_http_server, bakery_http_server):
    _, _, _, zarr_http_path, reference_ds, _, _ = bakery_http_server
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    name = list(bakery_database_entry)[0]
    if not invalid:
        b = Bakery(name=name, database_path=bakery_database_http_path)
        assert b.bakery_database.bakeries == {
            BakeryName(name=k): BakeryMeta(**v) for k, v in bakery_database_entry.items()
        }
        # check read access
        for run_id in b.build_logs.run_ids:
            # mapper not strictly necessary for http urls, but method is more generalized this way
            mapper = b.get_dataset_mapper(run_id)
            assert mapper.root == zarr_http_path
            ds = xr.open_zarr(mapper, consolidated=True)
            xr.testing.assert_identical(ds, reference_ds)
    elif invalid == "database_path":
        with pytest.raises(FileNotFoundError):
            path = bakery_database_http_path.replace("://", "")
            Bakery(name=name, database_path=path)
    elif invalid == "bakery_name":
        with pytest.raises(ValidationError):
            name = name.replace(".bakery.", "")
            Bakery(name=name, database_path=bakery_database_http_path)


@pytest.mark.parametrize("invalid", [None, "env_var_key", "env_var_value"])
def test_bakery_component_write_access(invalid, github_http_server, bakery_http_server):
    tempdir, http_base = bakery_http_server[:2]
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    name = list(bakery_database_entry)[0]

    if not invalid:
        b = Bakery(name=name, database_path=bakery_database_http_path, write_access=True)
        assert isinstance(b.credentialed_fs, HTTPFileSystem)

        content, src_path, dst_path, _ = write_test_file(tempdir, http_base)
        b.put(src_path, dst_path)

        r = b.cat(dst_path)
        assert ast.literal_eval(r.decode("utf-8")) == content

        with fsspec.open(dst_path) as f:
            d = json.loads(f.read())
        assert d == content

    elif invalid == "env_var_key":
        del os.environ["TEST_BAKERY_BASIC_AUTH"]
        with pytest.raises(KeyError):
            Bakery(name=name, database_path=bakery_database_http_path, write_access=True)
    elif invalid == "env_var_value":
        os.environ["TEST_BAKERY_BASIC_AUTH"] = "incorrect plain text auth string"
        b = Bakery(name=name, database_path=bakery_database_http_path, write_access=True)
        content, src_path, dst_path, _ = write_test_file(tempdir, http_base)
        with pytest.raises(ClientResponseError):
            b.put(src_path, dst_path)


@pytest.mark.parametrize("invalid", [None, "metadata_url_base", "feedstock_name"])
def test_feedstock_metadata(github_http_server, meta_yaml, invalid, invalid_feedstock_names):
    github_http_base, _, _ = github_http_server
    if not invalid:
        f = FeedstockMetadata(feedstock_id="mock-feedstock@1.0", metadata_url_base=github_http_base)
        assert f.metadata_dict == meta_yaml
    elif invalid == "metadata_url_base":
        with pytest.raises(FileNotFoundError):
            FeedstockMetadata(feedstock_id="mock-feedstock@1.0")
    elif invalid == "feedstock_name":
        for f_id in invalid_feedstock_names:
            with pytest.raises(ValidationError):
                FeedstockMetadata(feedstock_id=f_id, metadata_url_base=github_http_base)
