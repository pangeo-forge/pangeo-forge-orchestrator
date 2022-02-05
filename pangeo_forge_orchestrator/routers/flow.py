import importlib
import json
import logging
import os
from functools import wraps

import yaml
from dask_kubernetes.objects import make_pod_spec
from fastapi import APIRouter
from gcsfs import GCSFileSystem
from pangeo_forge_recipes.recipes.base import BaseRecipe
from pangeo_forge_recipes.storage import CacheFSSpecTarget, MetadataTarget
from prefect.executors.dask import DaskExecutor
from prefect.run_configs.kubernetes import KubernetesRun
from prefect.storage import GCS
from pydantic import BaseModel
from s3fs import S3FileSystem

REQUIRED_ENV_VARS = [
    "PROJECT_NAME",  # bakery project
    "GOOGLE_APPLICATION_CREDENTIALS",  # path to json creds for bakery project
    "STORAGE_NAME",  # bakery project bucket name
    "PANGEO_FORGE_OSN_KEY",
    "PANGEO_FORGE_OSN_SECRET",
    "BAKERY_IMAGE",  # Seems like this is how we'd set worker images dynamically?
    "PREFECT_PROJECT",
    "PREFECT__CLOUD__AUTH_TOKEN",
    "PREFECT__CLOUD__AGENT__LABELS",
]
for v in REQUIRED_ENV_VARS:
    if v not in os.environ:
        raise ValueError(f"Environment variable {v} not set. Required for flow registration.")

# TODO: this module is untested!
# We have deliberately accepted this techincal debt in order to get metrics up working quickly.
# Once we have some time for maintainance, we need to write tests for these endpoints.

flow_router = APIRouter()


class FlowCreate(BaseModel):
    recipe_module_name: str  # e.g. `"recipe.py"`
    flow_name: str  # a name for the created flow


def set_log_level(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.basicConfig()
        logging.getLogger("pangeo_forge_recipes").setLevel(level=logging.DEBUG)
        result = func(*args, **kwargs)
        return result

    return wrapper


def register_recipe(recipe: BaseRecipe, flow_name: str):
    storage_name = os.environ["STORAGE_NAME"]
    fs_gcs = GCSFileSystem(project=os.environ["PROJECT_NAME"], bucket=storage_name)
    fs_osn = S3FileSystem(
        key=os.environ["PANGEO_FORGE_OSN_KEY"],
        secret=os.environ["PANGEO_FORGE_OSN_SECRET"],
        client_kwargs=dict(endpoint_url="https://ncsa.osn.xsede.org"),
        default_cache_type="none",
        default_fill_cache=False,
        use_listings_cache=False,
    )
    target_base = "s3://Pangeo/pangeo-forge"
    recipe.target = MetadataTarget(fs_osn, root_path=f"{target_base}/pfcsb-test/{flow_name}")
    recipe.input_cache = CacheFSSpecTarget(fs_gcs, root_path=(f"{storage_name}/cache"))
    recipe.metadata_cache = MetadataTarget(fs_gcs, root_path=(f"{storage_name}/cache/metadata"))

    flow = recipe.to_prefect()

    job_template = yaml.safe_load(
        """
        apiVersion: batch/v1
        kind: Job
        metadata:
          annotations:
            "cluster-autoscaler.kubernetes.io/safe-to-evict": "false"
        spec:
          ttlSecondsAfterFinished: 100
          template:
            spec:
              containers:
                - name: flow
        """
    )
    flow.storage = GCS(bucket=f"{storage_name}")
    flow.run_config = KubernetesRun(
        job_template=job_template,
        image=os.environ["BAKERY_IMAGE"],
        labels=json.loads(os.environ["PREFECT__CLOUD__AGENT__LABELS"]),
        cpu_request="1000m",
        memory_request="3Gi",
    )
    flow.executor = DaskExecutor(
        cluster_class="dask_kubernetes.KubeCluster",
        cluster_kwargs={
            "pod_template": make_pod_spec(
                image=os.environ["BAKERY_IMAGE"],
                labels={"flow": flow_name},
                memory_limit="1Gi",
                memory_request="500Mi",
                cpu_limit="512m",
                cpu_request="256m",
            ),
        },
        adapt_kwargs={"maximum": 10},
    )

    for flow_task in flow.tasks:
        flow_task.run = set_log_level(flow_task.run)

    flow.name = flow_name
    project_name = os.environ["PREFECT_PROJECT"]
    flow.register(project_name=project_name)


@flow_router.post("/register-flow", summary="Register a Flow with Prefect Cloud")
def register_flow(
    *, flow_params: FlowCreate,
):
    flow_params_dict = flow_params.dict()
    module_name = flow_params_dict["recipe_module_name"]
    flow_name = flow_params_dict["flow_name"]

    # `importlib` usage based on `pangeo-forge-prefect.flow_manager::get_module_attribute`:
    # https://github.com/pangeo-forge/pangeo-forge-prefect/blob/a63777913757565209eee446cb1a4093de291b4a/pangeo_forge_prefect/flow_manager.py#L269-L279
    spec = importlib.util.spec_from_file_location(  # type: ignore
        module_name.split(".")[0], module_name,
    )
    recipe_module = importlib.util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(recipe_module)
    recipe = recipe_module.recipe

    register_recipe(recipe=recipe, flow_name=flow_name)
    return {
        "registered_flow_name": flow_name,
        "recipe": repr(recipe),
        "from_module": module_name,
    }
