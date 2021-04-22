import os
from unittest.mock import patch

from dask_cloudprovider.aws.ecs import FargateCluster
from prefect.run_configs import ECSRun

from pangeo_forge_prefect.flow_manager import (
    configure_dask_executor,
    configure_run_config,
    configure_targets,
)

from .data.classes import bakery, meta


@patch("pangeo_forge_prefect.flow_manager.S3FileSystem")
@patch.dict(os.environ, {"BUCKET_KEY": "key", "BUCKET_SECRET": "secret"})
def test_configure_targets(S3FileSystem):
    recipe_name = "test"
    targets = configure_targets(bakery, meta.bakery, recipe_name)
    S3FileSystem.assert_called_once_with(
        anon=False,
        default_cache_type="none",
        default_fill_cache=False,
        key="key",
        secret="secret",
    )
    assert targets.target.root_path == f"s3://{meta.bakery.target}/{recipe_name}/target"


def test_configure_dask_executor():
    recipe_name = "test"
    dask_executor = configure_dask_executor(bakery.cluster, meta.bakery, recipe_name)
    assert dask_executor.cluster_class == FargateCluster
    assert dask_executor.cluster_kwargs["worker_cpu"] == meta.bakery.resources.cpu
    assert dask_executor.cluster_kwargs["worker_mem"] == meta.bakery.resources.memory

    meta.bakery.resources = None
    dask_executor = configure_dask_executor(bakery.cluster, meta.bakery, recipe_name)
    # Uses default resource definitions
    assert dask_executor.cluster_kwargs["worker_cpu"] == 1024
    assert dask_executor.cluster_kwargs["worker_mem"] == 4096


def test_configure_run_config():
    recipe_name = "test"
    run_config = configure_run_config(bakery.cluster, meta.bakery, recipe_name)
    assert type(run_config) == ECSRun
    assert meta.bakery.id in run_config.labels
