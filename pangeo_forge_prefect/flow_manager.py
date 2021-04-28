import importlib
import logging
import os
from dataclasses import dataclass
from functools import wraps
from typing import Dict

import yaml
from dacite import from_dict
from pangeo_forge.storage import CacheFSSpecTarget, FSSpecTarget
from prefect import storage
from prefect.executors import DaskExecutor
from prefect.run_configs import ECSRun
from rechunker.executors import PrefectPipelineExecutor
from s3fs import S3FileSystem

from pangeo_forge_prefect.meta_types.bakery import (
    FARGATE_CLUSTER,
    S3_PROTOCOL,
    Bakery,
    Cluster,
)
from pangeo_forge_prefect.meta_types.meta import Meta, RecipeBakery


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


def set_log_level(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.basicConfig()
        logging.getLogger("pangeo_forge.recipes.xarray_zarr").setLevel(level=logging.DEBUG)
        result = func(*args, **kwargs)
        return result

    return wrapper


def configure_targets(bakery: Bakery, recipe_bakery: RecipeBakery, recipe_name: str, secrets: Dict):
    target = bakery.targets[recipe_bakery.target]
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
            target_path = f"s3://{recipe_bakery.target}/{recipe_name}/target"
            target = FSSpecTarget(fs, target_path)
            cache_path = f"s3://{recipe_bakery.target}/{recipe_name}/cache"
            cache_target = CacheFSSpecTarget(fs, cache_path)
            return Targets(target=target, cache=cache_target)
    else:
        raise UnsupportedTarget


def configure_dask_executor(cluster: Cluster, recipe_bakery: RecipeBakery, recipe_name: str):
    worker_cpu = recipe_bakery.resources.cpu if recipe_bakery.resources is not None else 1024
    worker_mem = recipe_bakery.resources.memory if recipe_bakery.resources is not None else 4096
    if cluster.type == FARGATE_CLUSTER:
        dask_executor = DaskExecutor(
            cluster_class="dask_cloudprovider.aws.FargateCluster",
            cluster_kwargs={
                "image": cluster.worker_image,
                "vpc": cluster.vpc,
                "cluster_arn": cluster.cluster_arn,
                "task_role_arn": cluster.task_role_arn,
                "execution_role_arn": cluster.execution_role_arn,
                "security_groups": cluster.security_groups,
                "n_workers": 4,
                "scheduler_cpu": 1024,
                "scheduler_mem": 2048,
                "worker_cpu": worker_cpu,
                "worker_mem": worker_mem,
                "scheduler_timeout": "15 minutes",
                "environment": {
                    "PREFECT__LOGGING__EXTRA_LOGGERS": "['pangeo_forge.recipes.xarray_zarr']"
                },
                "tags": {
                    "Project": "pangeo-forge",
                    "Recipe": recipe_name,
                },
            },
        )
        return dask_executor
    else:
        raise UnsupportedClusterType


def configure_run_config(cluster: Cluster, recipe_bakery: RecipeBakery, recipe_name: str):
    if cluster.type == FARGATE_CLUSTER:
        definition = {
            "networkMode": "awsvpc",
            "cpu": 1024,
            "memory": 2048,
            "containerDefinitions": [{"name": "flow"}],
            "executionRoleArn": cluster.execution_role_arn,
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
    else:
        raise UnsupportedClusterType


def configure_flow_storage(cluster: Cluster, secrets):
    key = secrets[cluster.flow_storage_options.key]
    secret = secrets[cluster.flow_storage_options.secret]
    if cluster.flow_storage_protocol == S3_PROTOCOL:
        flow_storage = storage.S3(
            bucket=cluster.flow_storage,
            client_options={"aws_access_key_id": key, "aws_secret_access_key": secret},
        )
        return flow_storage
    else:
        raise UnsupportedFlowStorage


def register_flow(meta_path: str, bakeries_path: str, secrets: Dict):
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

        for recipe_meta in meta.recipes:
            # Load module from meta.yaml
            meta_dir = os.path.dirname(os.path.abspath(meta_path))
            module_path = os.path.join(meta_dir, recipe_meta.module)
            spec = importlib.util.spec_from_file_location(recipe_meta.name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            recipe = module.recipe

            targets = configure_targets(bakery, meta.bakery, recipe_meta.id, secrets)
            recipe.target = targets.target
            recipe.input_cache = targets.cache
            recipe.metadata_cache = targets.target

            dask_executor = configure_dask_executor(bakery.cluster, meta.bakery, recipe_meta.id)
            executor = PrefectPipelineExecutor()
            pipeline = recipe.to_pipelines()
            flow = executor.pipelines_to_plan(pipeline)
            flow.storage = configure_flow_storage(bakery.cluster, secrets)
            run_config = configure_run_config(bakery.cluster, meta.bakery, recipe_meta.id)
            flow.run_config = run_config
            flow.executor = dask_executor

            for flow_task in flow.tasks:
                flow_task.run = set_log_level(flow_task.run)

            flow.name = recipe_meta.id
            project_name = os.environ["PREFECT_PROJECT_NAME"]
            flow.register(project_name=project_name)
