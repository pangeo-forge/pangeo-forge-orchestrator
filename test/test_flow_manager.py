import os
from unittest.mock import patch

import pytest
import yaml
from dacite import from_dict
from dask_cloudprovider.aws.ecs import FargateCluster
from prefect.run_configs import ECSRun

from pangeo_forge_prefect.flow_manager import (
    UnsupportedClusterType,
    UnsupportedFlowStorage,
    UnsupportedTarget,
    configure_dask_executor,
    configure_flow_storage,
    configure_run_config,
    configure_targets,
)
from pangeo_forge_prefect.meta_types.bakery import Bakery
from pangeo_forge_prefect.meta_types.meta import Meta


@pytest.fixture
def aws_bakery():
    with open(f"{os.path.dirname(__file__)}/data/bakeries.yaml") as bakeries_yaml:
        bakeries_dict = yaml.load(bakeries_yaml, Loader=yaml.FullLoader)
        test_aws_bakery = from_dict(
            data_class=Bakery,
            data=bakeries_dict["devseed.bakery.development.aws.us-west-2"],
        )
        return test_aws_bakery


@pytest.fixture
def meta():
    with open(f"{os.path.dirname(__file__)}/data/meta.yaml") as meta_yaml:
        meta_dict = yaml.load(meta_yaml, Loader=yaml.FullLoader)
        meta_class = from_dict(data_class=Meta, data=meta_dict)
        return meta_class


@patch("pangeo_forge_prefect.flow_manager.S3FileSystem")
def test_configure_targets(S3FileSystem, aws_bakery, meta):
    recipe_name = "test"
    key = "key"
    secret = "secret"
    secrets = {
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_KEY": key,
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_SECRET": secret,
    }
    targets = configure_targets(aws_bakery, meta.bakery, recipe_name, secrets)
    S3FileSystem.assert_called_once_with(
        anon=False,
        default_cache_type="none",
        default_fill_cache=False,
        key=key,
        secret=secret,
    )
    assert targets.target.root_path == f"s3://{meta.bakery.target}/{recipe_name}/target"
    aws_bakery.targets[
        "pangeo-forge-aws-bakery-flowcachebucketpangeofor-196cpck7y0pbl"
    ].private.protocol = "GCS"
    with pytest.raises(UnsupportedTarget):
        configure_targets(aws_bakery, meta.bakery, recipe_name, secrets)


@patch("pangeo_forge_prefect.flow_manager.storage")
def test_configure_flow_storage(storage, aws_bakery):
    key = "key"
    secret = "secret"
    secrets = {
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_KEY": key,
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_SECRET": secret,
    }
    configure_flow_storage(aws_bakery.cluster, secrets)
    storage.S3.assert_called_once_with(
        bucket=aws_bakery.cluster.flow_storage,
        client_options={"aws_access_key_id": key, "aws_secret_access_key": secret},
    )
    aws_bakery.cluster.flow_storage_protocol = "GCS"
    with pytest.raises(UnsupportedFlowStorage):
        configure_flow_storage(aws_bakery.cluster, secrets)


def test_configure_dask_executor(aws_bakery, meta):
    recipe_name = "test"
    dask_executor = configure_dask_executor(aws_bakery.cluster, meta.bakery, recipe_name)
    assert dask_executor.cluster_class == FargateCluster
    assert dask_executor.cluster_kwargs["worker_cpu"] == meta.bakery.resources.cpu
    assert dask_executor.cluster_kwargs["worker_mem"] == meta.bakery.resources.memory
    assert dask_executor.adapt_kwargs["maximum"] == aws_bakery.cluster.max_workers

    meta.bakery.resources = None
    dask_executor = configure_dask_executor(aws_bakery.cluster, meta.bakery, recipe_name)
    # Uses default resource definitions
    assert dask_executor.cluster_kwargs["worker_cpu"] == 1024
    assert dask_executor.cluster_kwargs["worker_mem"] == 4096
    aws_bakery.cluster.type = "New"
    with pytest.raises(UnsupportedClusterType):
        dask_executor = configure_dask_executor(aws_bakery.cluster, meta.bakery, recipe_name)


def test_configure_run_config(aws_bakery, meta):
    recipe_name = "test"
    run_config = configure_run_config(aws_bakery.cluster, meta.bakery, recipe_name)
    assert type(run_config) == ECSRun
    assert meta.bakery.id in run_config.labels
    aws_bakery.cluster.type = "New"
    with pytest.raises(UnsupportedClusterType):
        configure_dask_executor(aws_bakery.cluster, meta.bakery, recipe_name)
