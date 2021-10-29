import ast
import os

import pytest
import xarray as xr
from aiohttp.client_exceptions import ClientResponseError
from fsspec.implementations.http import HTTPFileSystem
from pydantic import ValidationError

from pangeo_forge_orchestrator.components import Bakery, FeedstockMetadata
from pangeo_forge_orchestrator.meta_types.bakery import BakeryMeta

from .test_server import write_test_file


@pytest.mark.parametrize("invalid", [None, "database_path", "bakery_name"])
def test_bakery_component_read_only(invalid, github_http_server, bakery_http_server):
    _, _, _, zarr_http_path, reference_ds, _, _ = bakery_http_server
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    name = list(bakery_database_entry)[0]
    if not invalid:
        b = Bakery(name=name, path=bakery_database_http_path)
        assert b.bakeries == bakery_database_entry
        # ensure the bakery's metadata is valid; is this sufficiently tested elsewhere?
        bakery_name = list(b.bakeries)[0]
        bm = BakeryMeta(**b.bakeries[bakery_name])
        assert bm is not None
        # check read access
        for run_id in b.build_logs.run_ids:
            # mapper not strictly necessary for http urls, but method is more generalized this way
            mapper = b.get_dataset_mapper(run_id)
            assert mapper.root == zarr_http_path
            ds = xr.open_zarr(mapper, consolidated=True)
            xr.testing.assert_identical(ds, reference_ds)
    elif invalid == "database_path":
        with pytest.raises(ValidationError):
            path = bakery_database_http_path.replace("://", "")
            Bakery(name=name, path=path)
    elif invalid == "bakery_name":
        with pytest.raises(ValidationError):
            name = name.replace(".bakery.", "")
            Bakery(name=name, path=bakery_database_http_path)


@pytest.mark.parametrize("invalid", [None, "env_var_key", "env_var_value"])
def test_bakery_component_write_access(invalid, github_http_server, bakery_http_server):
    tempdir, http_base = bakery_http_server[:2]
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    name = list(bakery_database_entry)[0]

    if not invalid:
        b = Bakery(name=name, path=bakery_database_http_path, write_access=True)
        assert isinstance(b.credentialed_fs, HTTPFileSystem)

        content, src_path, dst_path, _ = write_test_file(tempdir, http_base)
        b.put(src_path, dst_path)
        r = b.cat(dst_path)
        assert ast.literal_eval(r.decode("utf-8")) == content

    elif invalid == "env_var_key":
        del os.environ["TEST_BAKERY_BASIC_AUTH"]
        with pytest.raises(KeyError):
            Bakery(name=name, path=bakery_database_http_path, write_access=True)
    elif invalid == "env_var_value":
        os.environ["TEST_BAKERY_BASIC_AUTH"] = "incorrect plain text auth string"
        b = Bakery(name=name, path=bakery_database_http_path, write_access=True)
        content, src_path, dst_path, _ = write_test_file(tempdir, http_base)
        with pytest.raises(ClientResponseError):
            b.put(src_path, dst_path)


def test_feedstock_metadata():
    f_id = "noaa-oisst-avhrr-only-feedstock@1.0"
    f = FeedstockMetadata(feedstock_id=f_id)
    assert f is not None
