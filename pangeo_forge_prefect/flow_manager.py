import importlib
import logging
import os
from dataclasses import dataclass
from functools import wraps
from typing import Dict

import yaml
from adlfs import AzureBlobFileSystem
from dacite import from_dict
from dask_kubernetes.objects import make_pod_spec
from pangeo_forge_recipes.recipes import XarrayZarrRecipe
from pangeo_forge_recipes.recipes.base import BaseRecipe
from pangeo_forge_recipes.storage import CacheFSSpecTarget, FSSpecTarget
from prefect import storage
from prefect.executors import DaskExecutor
from prefect.run_configs import ECSRun, KubernetesRun
from rechunker.executors import PrefectPipelineExecutor
from s3fs import S3FileSystem

from pangeo_forge_prefect.meta_types.bakery import (
    ABFS_PROTOCOL,
    AKS_CLUSTER,
    FARGATE_CLUSTER,
    S3_PROTOCOL,
    Bakery,
    Cluster,
)
from pangeo_forge_prefect.meta_types.meta import Meta, RecipeBakery
from pangeo_forge_prefect.meta_types.versions import Versions


@dataclass
class Targets:
    target: FSSpecTarget
    cache: CacheFSSpecTarget


class UnsupportedTarget(Exception):
    pass


class UnsupportedClusterType(Exception):
    pass


class UnsupportedFlowStorage(Exception):
    pass


class UnsupportedPangeoVersion(Exception):
    pass


class UnsupportedPangeoForgeRecipeVersion(Exception):
    pass


class UnsupportedPrefectVersion(Exception):
    pass


class UnsupportedRecipeType(Exception):
    pass


def set_log_level(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.basicConfig()
        logging.getLogger("pangeo_forge_recipes").setLevel(level=logging.DEBUG)
        result = func(*args, **kwargs)
        return result

    return wrapper


def configure_targets(
    bakery: Bakery, recipe_bakery: RecipeBakery, recipe_name: str, secrets: Dict, extension: str
):
    target = bakery.targets[recipe_bakery.target]
    repository = secrets["GITHUB_REPOSITORY"]
    if target.private.protocol == S3_PROTOCOL:
        if target.private.storage_options:
            key = secrets[target.private.storage_options.key]
            secret = secrets[target.private.storage_options.secret]
            fs = S3FileSystem(
                anon=False,
                default_cache_type="none",
                default_fill_cache=False,
                key=key,
                secret=secret,
            )
            target_path = (
                f"s3://{recipe_bakery.target}/pangeo-forge/{repository}/{recipe_name}.{extension}"
            )
            target = FSSpecTarget(fs, target_path)
            cache_path = f"s3://{recipe_bakery.target}/{recipe_name}/cache"
            cache_target = CacheFSSpecTarget(fs, cache_path)
            return Targets(target=target, cache=cache_target)
    elif target.private.protocol == ABFS_PROTOCOL:
        if target.private.storage_options:
            secret = secrets[target.private.storage_options.secret]
            fs = AzureBlobFileSystem(connection_string=secret)
            target_path = (
                f"abfs://{recipe_bakery.target}/pangeo-forge/{repository}/{recipe_name}.{extension}"
            )
            target = FSSpecTarget(fs, target_path)
            cache_path = f"abfs://{recipe_bakery.target}/{recipe_name}/cache"
            cache_target = CacheFSSpecTarget(fs, cache_path)
            return Targets(target=target, cache=cache_target)
    else:
        raise UnsupportedTarget


def configure_dask_executor(
    cluster: Cluster, recipe_bakery: RecipeBakery, recipe_name: str, secrets: Dict
):
    if cluster.type == FARGATE_CLUSTER:
        worker_cpu = recipe_bakery.resources.cpu if recipe_bakery.resources is not None else 1024
        worker_mem = recipe_bakery.resources.memory if recipe_bakery.resources is not None else 4096
        dask_executor = DaskExecutor(
            cluster_class="dask_cloudprovider.aws.FargateCluster",
            cluster_kwargs={
                "image": cluster.worker_image,
                "vpc": cluster.cluster_options.vpc,
                "cluster_arn": cluster.cluster_options.cluster_arn,
                "task_role_arn": cluster.cluster_options.task_role_arn,
                "execution_role_arn": cluster.cluster_options.execution_role_arn,
                "security_groups": cluster.cluster_options.security_groups,
                "scheduler_cpu": 1024,
                "scheduler_mem": 2048,
                "worker_cpu": worker_cpu,
                "worker_mem": worker_mem,
                "scheduler_timeout": "15 minutes",
                "environment": {"PREFECT__LOGGING__EXTRA_LOGGERS": "['pangeo_forge_recipes']"},
                "tags": {
                    "Project": "pangeo-forge",
                    "Recipe": recipe_name,
                },
            },
            adapt_kwargs={"maximum": cluster.max_workers},
        )
        return dask_executor
    elif cluster.type == AKS_CLUSTER:
        worker_cpu = recipe_bakery.resources.cpu if recipe_bakery.resources is not None else 250
        worker_mem = recipe_bakery.resources.memory if recipe_bakery.resources is not None else 512
        dask_executor = DaskExecutor(
            cluster_class="dask_kubernetes.KubeCluster",
            cluster_kwargs={
                "pod_template": make_pod_spec(
                    image=cluster.worker_image,
                    labels={"Recipe": recipe_name, "Project": "pangeo-forge"},
                    memory_request=f"{worker_mem}Mi",
                    cpu_request=f"{worker_cpu}m",
                    env={
                        "AZURE_STORAGE_CONNECTION_STRING": secrets[
                            cluster.flow_storage_options.secret
                        ]
                    },
                )
            },
            adapt_kwargs={"maximum": cluster.max_workers},
        )
        return dask_executor
    else:
        raise UnsupportedClusterType


def configure_run_config(
    cluster: Cluster, recipe_bakery: RecipeBakery, recipe_name: str, secrets: Dict
):
    if cluster.type == FARGATE_CLUSTER:
        definition = {
            "networkMode": "awsvpc",
            "cpu": 1024,
            "memory": 2048,
            "containerDefinitions": [{"name": "flow"}],
            "executionRoleArn": cluster.cluster_options.execution_role_arn,
        }
        run_config = ECSRun(
            image=cluster.worker_image,
            labels=[recipe_bakery.id],
            task_definition=definition,
            run_task_kwargs={
                "tags": [
                    {"key": "Project", "value": "pangeo-forge"},
                    {"key": "Recipe", "value": recipe_name},
                ]
            },
        )
        return run_config
    elif cluster.type == AKS_CLUSTER:
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
        run_config = KubernetesRun(
            job_template=job_template,
            image=cluster.worker_image,
            labels=[recipe_bakery.id],
            cpu_request="1000m",
            memory_request="2048Mi",
            env={"AZURE_STORAGE_CONNECTION_STRING": secrets[cluster.flow_storage_options.secret]},
        )
        return run_config
    else:
        raise UnsupportedClusterType


def configure_flow_storage(cluster: Cluster, secrets):
    if cluster.flow_storage_protocol == S3_PROTOCOL:
        key = secrets[cluster.flow_storage_options.key]
        secret = secrets[cluster.flow_storage_options.secret]
        flow_storage = storage.S3(
            bucket=cluster.flow_storage,
            client_options={"aws_access_key_id": key, "aws_secret_access_key": secret},
        )
        return flow_storage
    elif cluster.flow_storage_protocol == ABFS_PROTOCOL:
        secret = secrets[cluster.flow_storage_options.secret]
        flow_storage = storage.Azure(container=cluster.flow_storage, connection_string=secret)
        return flow_storage
    else:
        raise UnsupportedFlowStorage


def check_versions(meta: Meta, cluster: Cluster, versions: Versions):
    if meta.pangeo_notebook_version != versions.pangeo_notebook_version:
        raise UnsupportedPangeoVersion
    elif meta.pangeo_notebook_version != cluster.pangeo_notebook_version:
        raise UnsupportedPangeoVersion
    elif meta.pangeo_forge_version != versions.pangeo_forge_version:
        raise UnsupportedPangeoForgeRecipeVersion
    elif meta.pangeo_forge_version != cluster.pangeo_forge_version:
        raise UnsupportedPangeoForgeRecipeVersion
    elif versions.prefect_version != cluster.prefect_version:
        raise UnsupportedPrefectVersion
    else:
        return True


def get_module_attribute(meta_path: str, attribute_path: str):
    module_components = attribute_path.split(":")
    module = f"{module_components[0]}.py"
    name = module_components[1]

    meta_dir = os.path.dirname(os.path.abspath(meta_path))
    module_path = os.path.join(meta_dir, module)
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


def get_target_extension(recipe: BaseRecipe) -> str:
    if isinstance(recipe, XarrayZarrRecipe):
        return "zarr"
    else:
        raise UnsupportedRecipeType


def recipe_to_flow(
    bakery: Bakery, meta: Meta, recipe_id: str, recipe: BaseRecipe, targets: Targets, secrets: Dict
):
    recipe.target = targets.target
    recipe.input_cache = targets.cache
    recipe.metadata_cache = targets.target

    dask_executor = configure_dask_executor(bakery.cluster, meta.bakery, recipe_id, secrets)
    executor = PrefectPipelineExecutor()
    pipeline = recipe.to_pipelines()
    flow = executor.pipelines_to_plan(pipeline)
    flow.storage = configure_flow_storage(bakery.cluster, secrets)
    run_config = configure_run_config(bakery.cluster, meta.bakery, recipe_id, secrets)
    flow.run_config = run_config
    flow.executor = dask_executor

    for flow_task in flow.tasks:
        flow_task.run = set_log_level(flow_task.run)

    flow.name = recipe_id
    project_name = os.environ["PREFECT_PROJECT_NAME"]
    flow.register(project_name=project_name)


def register_flow(meta_path: str, bakeries_path: str, secrets: Dict, versions: Versions):
    """
    Convert a pangeo-forge to a Prefect recipe and register with Prefect Cloud.

    Uses values from a recipe's meta.yaml, values from a bakeries.yaml
    file and a dictionary of pangeo-forge bakery secrets to configure the
    storage, dask cluster and parameters for a Prefect flow and registers this
    flow with a Prefect Cloud account.

    Parameters
    ----------
    meta_path : str
        Path to a recipe's meta.yaml file
    bakeries_path : str
        Path to a bakeries.yaml file containing an entry for the recipe's
        bakery.id
    """
    with open(meta_path) as meta_yaml, open(bakeries_path) as bakeries_yaml:
        meta_dict = yaml.load(meta_yaml, Loader=yaml.FullLoader)
        meta = from_dict(data_class=Meta, data=meta_dict)

        bakeries_dict = yaml.load(bakeries_yaml, Loader=yaml.FullLoader)
        bakery = from_dict(data_class=Bakery, data=bakeries_dict[meta.bakery.id])

        check_versions(meta, bakery.cluster, versions)

        for recipe_meta in meta.recipes:
            if recipe_meta.dict_object:
                recipes_dict = get_module_attribute(meta_path, recipe_meta.dict_object)
                for key, value in recipes_dict.items():
                    extension = get_target_extension(value)
                    targets = configure_targets(bakery, meta.bakery, key, secrets, extension)
                    recipe_to_flow(bakery, meta, key, value, targets, secrets)
            else:
                recipe = get_module_attribute(meta_path, recipe_meta.object)
                extension = get_target_extension(recipe)
                targets = configure_targets(bakery, meta.bakery, recipe_meta.id, secrets, extension)
                recipe_to_flow(bakery, meta, recipe_meta.id, recipe, targets, secrets)
