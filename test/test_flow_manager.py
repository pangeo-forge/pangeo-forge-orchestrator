import os
import pathlib
from unittest.mock import Mock, patch

import fsspec
import pytest
import yaml
from dacite import from_dict
from dask_cloudprovider.aws.ecs import FargateCluster
from dask_kubernetes import KubeCluster
from pangeo_forge_recipes.recipes import XarrayZarrRecipe
from pangeo_forge_recipes.storage import CacheFSSpecTarget, FSSpecTarget
from prefect.core import Flow
from prefect.run_configs import ECSRun, KubernetesRun

from pangeo_forge_prefect.flow_manager import (
    Targets,
    UnsupportedClusterType,
    UnsupportedFlowStorage,
    UnsupportedPangeoVersion,
    UnsupportedRecipeType,
    UnsupportedTarget,
    check_versions,
    configure_dask_executor,
    configure_flow_storage,
    configure_run_config,
    configure_targets,
    get_module_attribute,
    get_target_extension,
    recipe_to_flow,
)
from pangeo_forge_prefect.meta_types.bakery import Bakery
from pangeo_forge_prefect.meta_types.meta import Meta
from pangeo_forge_prefect.meta_types.versions import Versions

from .data.recipe import recipe as recipe_class


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
def azure_bakery():
    with open(f"{os.path.dirname(__file__)}/data/bakeries.yaml") as bakeries_yaml:
        bakeries_dict = yaml.load(bakeries_yaml, Loader=yaml.FullLoader)
        test_azure_bakery = from_dict(
            data_class=Bakery,
            data=bakeries_dict["devseed.bakery.development.azure.ukwest"],
        )
        return test_azure_bakery


@pytest.fixture
def meta_aws():
    with open(f"{os.path.dirname(__file__)}/data/meta_aws.yaml") as meta_yaml:
        meta_dict = yaml.load(meta_yaml, Loader=yaml.FullLoader)
        meta_class = from_dict(data_class=Meta, data=meta_dict)
        return meta_class


@pytest.fixture
def meta_azure():
    with open(f"{os.path.dirname(__file__)}/data/meta_azure.yaml") as meta_yaml:
        meta_dict = yaml.load(meta_yaml, Loader=yaml.FullLoader)
        meta_class = from_dict(data_class=Meta, data=meta_dict)
        return meta_class


@pytest.fixture
def k8s_job_template():
    job_template = yaml.safe_load(
        """
        apiVersion: batch/v1
        kind: Job
        metadata:
          annotations:
            "cluster-autoscaler.kubernetes.io/safe-to-evict": "false"
        spec:
          template:
            spec:
              containers:
                - name: flow
        """
    )
    return job_template


recipe_name = "test"
key = "key"
secret = "secret"
extension = "zarr"


@pytest.fixture
def secrets():
    secret_values = {
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_KEY": key,
        "DEVSEED_BAKERY_DEVELOPMENT_AWS_US_WEST_2_SECRET": secret,
        "DEVSEED_BAKERY_DEVELOPMENT_AZURE_UKWEST_CONNECTION_STRING": secret,
        "GITHUB_REPOSITORY": "staged-recipes",
    }
    return secret_values


@pytest.fixture()
def tmp_target(tmpdir_factory):
    fs = fsspec.get_filesystem_class("file")()
    path = str(tmpdir_factory.mktemp("target"))
    return FSSpecTarget(fs, path)


@pytest.fixture()
def tmp_cache(tmpdir_factory):
    path = str(tmpdir_factory.mktemp("cache"))
    fs = fsspec.get_filesystem_class("file")()
    cache = CacheFSSpecTarget(fs, path)
    return cache


@patch.dict(os.environ, {"GITHUB_REPOSITORY": "pangeo-forge/staged-recipes"})
@patch("pangeo_forge_prefect.flow_manager.S3FileSystem")
def test_configure_targets_aws(S3FileSystem, aws_bakery, meta_aws, secrets):
    targets = configure_targets(aws_bakery, meta_aws.bakery, recipe_name, secrets, extension)
    S3FileSystem.assert_called_once_with(
        anon=False,
        default_cache_type="none",
        default_fill_cache=False,
        key=key,
        secret=secret,
    )
    assert targets.target.root_path == (
        f"s3://{meta_aws.bakery.target}/pangeo-forge/staged-recipes/{recipe_name}.zarr"
    )
    aws_bakery.targets[
        "pangeo-forge-aws-bakery-flowcachebucketdasktest4-10neo67y7a924"
    ].private.protocol = "GCS"
    with pytest.raises(UnsupportedTarget):
        configure_targets(aws_bakery, meta_aws.bakery, recipe_name, secrets, extension)


@patch.dict(os.environ, {"GITHUB_REPOSITORY": "pangeo-forge/staged-recipes"})
@patch("pangeo_forge_prefect.flow_manager.AzureBlobFileSystem")
def test_configure_targets_azure(AzureBlobFileSystem, azure_bakery, meta_azure, secrets):
    targets = configure_targets(azure_bakery, meta_azure.bakery, recipe_name, secrets, extension)
    AzureBlobFileSystem.assert_called_once_with(
        connection_string=secret,
    )
    assert targets.target.root_path == (
        f"abfs://{meta_azure.bakery.target}/pangeo-forge/staged-recipes/{recipe_name}.zarr"
    )
    azure_bakery.targets["test-bakery-flow-cache-container"].private.protocol = "GCS"
    with pytest.raises(UnsupportedTarget):
        configure_targets(azure_bakery, meta_azure.bakery, recipe_name, secrets, extension)


@patch("pangeo_forge_prefect.flow_manager.storage")
def test_configure_flow_storage_aws(storage, aws_bakery, secrets):
    configure_flow_storage(aws_bakery.cluster, secrets)
    storage.S3.assert_called_once_with(
        bucket=aws_bakery.cluster.flow_storage,
        client_options={"aws_access_key_id": key, "aws_secret_access_key": secret},
    )
    aws_bakery.cluster.flow_storage_protocol = "GCS"
    with pytest.raises(UnsupportedFlowStorage):
        configure_flow_storage(aws_bakery.cluster, secrets)


@patch("pangeo_forge_prefect.flow_manager.storage")
def test_configure_flow_storage_azure(storage, azure_bakery, secrets):
    configure_flow_storage(azure_bakery.cluster, secrets)
    storage.Azure.assert_called_once_with(
        container=azure_bakery.cluster.flow_storage,
        connection_string=secret,
    )
    azure_bakery.cluster.flow_storage_protocol = "GCS"
    with pytest.raises(UnsupportedFlowStorage):
        configure_flow_storage(azure_bakery.cluster, secrets)


def test_configure_dask_executor_aws(aws_bakery, meta_aws):
    recipe_name = "test"
    dask_executor = configure_dask_executor(aws_bakery.cluster, meta_aws.bakery, recipe_name, {})
    assert dask_executor.cluster_class == FargateCluster
    assert dask_executor.cluster_kwargs["worker_cpu"] == meta_aws.bakery.resources.cpu
    assert dask_executor.cluster_kwargs["worker_mem"] == meta_aws.bakery.resources.memory
    assert dask_executor.adapt_kwargs["maximum"] == aws_bakery.cluster.max_workers

    meta_aws.bakery.resources = None
    dask_executor = configure_dask_executor(aws_bakery.cluster, meta_aws.bakery, recipe_name, {})
    # Uses default resource definitions
    assert dask_executor.cluster_kwargs["worker_cpu"] == 1024
    assert dask_executor.cluster_kwargs["worker_mem"] == 4096
    aws_bakery.cluster.type = "New"
    with pytest.raises(UnsupportedClusterType):
        dask_executor = configure_dask_executor(
            aws_bakery.cluster, meta_aws.bakery, recipe_name, {}
        )


@patch("pangeo_forge_prefect.flow_manager.make_pod_spec")
def test_configure_dask_executor_azure(make_pod_spec, azure_bakery, meta_azure, secrets):
    dask_executor = configure_dask_executor(
        azure_bakery.cluster, meta_azure.bakery, recipe_name, secrets
    )
    assert dask_executor.cluster_class == KubeCluster
    assert dask_executor.adapt_kwargs["maximum"] == azure_bakery.cluster.max_workers
    make_pod_spec.assert_called_once_with(
        image=azure_bakery.cluster.worker_image,
        labels={"Recipe": recipe_name, "Project": "pangeo-forge"},
        memory_request=f"{meta_azure.bakery.resources.memory}Mi",
        cpu_request=f"{meta_azure.bakery.resources.cpu}m",
        env={"AZURE_STORAGE_CONNECTION_STRING": secret},
    )
    make_pod_spec.reset_mock()

    meta_azure.bakery.resources = None
    dask_executor = configure_dask_executor(
        azure_bakery.cluster, meta_azure.bakery, recipe_name, secrets
    )
    make_pod_spec.assert_called_once_with(
        image=azure_bakery.cluster.worker_image,
        labels={"Recipe": recipe_name, "Project": "pangeo-forge"},
        memory_request="512Mi",
        cpu_request="250m",
        env={"AZURE_STORAGE_CONNECTION_STRING": secret},
    )

    azure_bakery.cluster.type = "New"
    with pytest.raises(UnsupportedClusterType):
        dask_executor = configure_dask_executor(
            azure_bakery.cluster, meta_azure.bakery, recipe_name, {}
        )


def test_configure_run_config_aws(aws_bakery, meta_aws):
    recipe_name = "test"
    run_config = configure_run_config(aws_bakery.cluster, meta_aws.bakery, recipe_name, {})
    assert type(run_config) == ECSRun
    assert meta_aws.bakery.id in run_config.labels
    aws_bakery.cluster.type = "New"
    with pytest.raises(UnsupportedClusterType):
        configure_run_config(aws_bakery.cluster, meta_aws.bakery, recipe_name, {})


def test_configure_run_config_azure(azure_bakery, meta_azure, k8s_job_template, secrets):
    run_config = configure_run_config(azure_bakery.cluster, meta_azure.bakery, recipe_name, secrets)
    assert type(run_config) == KubernetesRun
    assert meta_azure.bakery.id in run_config.labels
    assert k8s_job_template == run_config.job_template
    assert azure_bakery.cluster.worker_image == run_config.image
    assert "1000m" == run_config.cpu_request
    assert "2048Mi" == run_config.memory_request
    assert {"AZURE_STORAGE_CONNECTION_STRING": secret} == run_config.env
    azure_bakery.cluster.type = "New"
    with pytest.raises(UnsupportedClusterType):
        configure_run_config(azure_bakery.cluster, meta_azure.bakery, recipe_name, {})


def test_check_versions(aws_bakery, meta_aws):
    versions = Versions(
        pangeo_notebook_version="2021.06.05",
        pangeo_forge_version="0.4.0",
        prefect_version="0.14.22",
    )
    assert check_versions(meta_aws, aws_bakery.cluster, versions)
    versions.pangeo_notebook_version = "none"
    with pytest.raises(UnsupportedPangeoVersion):
        check_versions(meta_aws, aws_bakery.cluster, versions)


def test_get_module_attribute(meta_aws):
    meta_path = pathlib.Path(__file__).parent.absolute().joinpath("./data/meta.yaml")

    recipe = get_module_attribute(meta_path, meta_aws.recipes[-1].object)
    assert isinstance(recipe, XarrayZarrRecipe)

    recipes_dict = get_module_attribute(meta_path, "recipe_dict:recipes")
    assert isinstance(recipes_dict, dict)


def test_get_target_extension():
    extension = get_target_extension(recipe_class)
    assert extension == "zarr"

    with pytest.raises(UnsupportedRecipeType):
        get_target_extension({})


@patch.dict(os.environ, {"PREFECT_PROJECT_NAME": "project"})
def test_recipe_to_flow(aws_bakery, meta_aws, secrets, tmp_target, tmp_cache):
    meta_path = pathlib.Path(__file__).parent.absolute().joinpath("./data/meta.yaml")
    recipe = get_module_attribute(meta_path, meta_aws.recipes[-1].object)

    targets = Targets(target=tmp_target, cache=tmp_cache)

    flow = recipe_to_flow(aws_bakery, meta_aws, "recipe_id", recipe, targets, secrets)
    assert isinstance(flow, Flow)

    recipe = Mock()
    flow_stub = Mock(tasks=[])
    recipe.copy_pruned().to_prefect.return_value = flow_stub
    recipe_to_flow(aws_bakery, meta_aws, "recipe_id", recipe, targets, secrets, prune=True)
    recipe.copy_pruned.assert_called_once
