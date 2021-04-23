from unittest.mock import patch

from dask_cloudprovider.aws.ecs import FargateCluster
from prefect.run_configs import ECSRun

from pangeo_forge_prefect.flow_manager import (
    configure_dask_executor,
    configure_flow_storage,
    configure_run_config,
    configure_targets,
)

from .data.classes import bakery, meta


@patch("pangeo_forge_prefect.flow_manager.S3FileSystem")
def test_configure_targets(S3FileSystem):
    recipe_name = "test"
    key = "key"
    secret = "secret"
    secrets = {
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_KEY": key,
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_SECRET": secret,
    }
    targets = configure_targets(bakery, meta.bakery, recipe_name, secrets)
    S3FileSystem.assert_called_once_with(
        anon=False,
        default_cache_type="none",
        default_fill_cache=False,
        key=key,
        secret=secret,
    )
    assert targets.target.root_path == f"s3://{meta.bakery.target}/{recipe_name}/target"


@patch("pangeo_forge_prefect.flow_manager.storage")
def test_configure_flow_storage(storage):
    key = "key"
    secret = "secret"
    secrets = {
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_KEY": key,
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_SECRET": secret,
    }
    configure_flow_storage(bakery.cluster, secrets)
    storage.S3.assert_called_once_with(
        bucket=bakery.cluster.flow_storage,
        client_options={"aws_access_key_id": key, "aws_secret_access_key": secret},
    )


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
