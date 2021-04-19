import importlib
import logging
import os
from dataclasses import dataclass
from functools import wraps

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


def set_log_level(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.basicConfig()
        logging.getLogger("pangeo_forge.recipe").setLevel(level=logging.DEBUG)
        result = func(*args, **kwargs)
        return result

    return wrapper


def configure_targets(bakery: Bakery, recipe_bakery: RecipeBakery, recipe_name: str):
    target = bakery.targets[recipe_bakery.target]
    if target.private.protocol == S3_PROTOCOL:
        if (target.private.storage_options.key) is None:
            fs = S3FileSystem(
                anon=False,
                default_cache_type="none",
                default_fill_cache=False,
            )
            target_path = f"s3://{recipe_bakery.target}/{recipe_name}/target"
            target = FSSpecTarget(fs, target_path)
            cache_path = f"s3://{recipe_bakery.target}/{recipe_name}/cache"
            cache_target = CacheFSSpecTarget(fs, cache_path)
            return Targets(target=target, cache=cache_target)


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
                "environment": {"PREFECT__LOGGING__EXTRA_LOGGERS": "['pangeo_forge.recipe']"},
                "tags": {
                    "Project": "pangeo-forge",
                    "Recipe": recipe_name,
                },
            },
        )
        return dask_executor


def configure_run_config(cluster: Cluster, recipe_name: str):
    definition = {
        "networkMode": "awsvpc",
        "cpu": 1024,
        "memory": 2048,
        "containerDefinitions": [{"name": "flow"}],
        "executionRoleArn": cluster.execution_role_arn,
    }
    run_config = ECSRun(
        image=cluster.worker_image,
        # Fix this to use bakery.id
        labels=["dask_test"],
        task_definition=definition,
        run_task_kwargs={
            "tags": [
                {"key": "Project", "value": "pangeo-forge"},
                {"key": "Recipe", "value": recipe_name},
            ]
        },
    )
    return run_config


def register_flow(meta_path, bakeries_path):
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

            targets = configure_targets(bakery, meta.bakery, recipe_meta.id)
            recipe.target = targets.target
            recipe.input_cache = targets.cache
            recipe.metadata_cache = targets.target

            dask_executor = configure_dask_executor(bakery.cluster, meta.bakery, recipe_meta.id)
            executor = PrefectPipelineExecutor()
            pipeline = recipe.to_pipelines()
            flow = executor.pipelines_to_plan(pipeline)
            flow.storage = storage.S3(bucket=bakery.cluster.flow_storage)
            run_config = configure_run_config(bakery.cluster, recipe_meta.id)
            flow.run_config = run_config
            flow.executor = dask_executor

            for flow_task in flow.tasks:
                flow_task.run = set_log_level(flow_task.run)

            flow.name = recipe_meta.id
            flow.register(project_name="pangeo-forge-aws-bakery")


register_flow("./test/data/meta.yaml", "./test/data/bakeries.yaml")
