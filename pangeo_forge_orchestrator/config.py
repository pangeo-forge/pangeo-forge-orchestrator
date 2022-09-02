import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel


class FastAPIConfig(BaseModel):
    ADMIN_API_KEY_SHA256: str
    ENCRYPTION_SALT: str
    PANGEO_FORGE_API_KEY: str


class GitHubAppConfig(BaseModel):
    id: int
    webhook_secret: str
    private_key: str
    run_only_on: Optional[List[str]] = None


class Bake(BaseModel):
    bakery_class: str
    job_name: Optional[str]


class Storage(BaseModel):
    fsspec_class: str
    fsspec_args: dict
    root_path: str
    public_url: Optional[str]


class DataflowBakery(BaseModel):
    temp_gcs_location: str


class Bakery(BaseModel):
    Bake: Bake
    TargetStorage: Storage
    InputCacheStorage: Storage
    MetadataCacheStorage: Storage
    DataflowBakery: Optional[DataflowBakery]
    secret_env: Optional[dict]


class Config(BaseModel):
    fastapi: FastAPIConfig
    github_app: GitHubAppConfig
    bakeries: Dict[str, Bakery]


root = Path(__file__).resolve().parent.parent


def get_app_config_path() -> str:
    deployment = os.environ.get("PANGEO_FORGE_DEPLOYMENT")
    if not deployment:
        raise ValueError("Env var PANGEO_FORGE_DEPLOYMENT must be set, but is not.")
    persistent_deployments = {
        "prod": "pangeo-forge",
        "staging": "pangeo-forge-staging",
    }
    if deployment in list(persistent_deployments):
        app_name = persistent_deployments[deployment]
    else:
        # this is an ephemeral deployment, so the name should be passed explicitly in the env
        app_name = deployment
    # The pre-commit-hook-ensure-sops hook installed in this repo's .pre-commit-config.yaml will
    # prevent commiting unencyrpted secrets to this directory.
    return f"{root}/secrets/config.{app_name}.yaml"


def get_config() -> Config:
    # bakeries public config files are organized like this
    #   ```
    #   ├── bakeries
    #   │   ├── pangeo-forge-ldeo-earthcube.pforge-local-cisaacstern.yaml
    #   │   ├── pangeo-forge-ldeo-earthcube.review-80.yaml
    #   │   ├── pangeo-forge-ldeo-earthcube.pangeo-forge-staging.yaml
    #   │   ├── pangeo-forge-ldeo-earthcube.pangeo-forge.yaml
    #   ```
    # so the following retrieves only the bakery config for the current deployment.
    # bakeries may want to customize their config on a per-deployment basis, for example if staging
    # storage is a different location from production storage (which it ideally should be).
    bakery_config_paths = [
        p
        for p in os.listdir(f"{root}/bakeries")
        if p.split(".")[1] == os.environ.get("PANGEO_FORGE_DEPLOYMENT")
    ]
    bakery_kws = {}
    for p in bakery_config_paths:
        with open(f"{root}/bakeries/{p}") as f:
            bakery_kws.update({p.split(".")[0]: yaml.safe_load(f)})

    bakeries = {k: Bakery(**v) for k, v in bakery_kws.items()}

    bakery_env_paths = [p for p in os.listdir(f"{root}/secrets") if p.startswith("bakery-env")]
    for p in bakery_env_paths:
        bakery_name = p.split(".")[1]
        with open(f"{root}/secrets/{p}") as f:
            env = yaml.safe_load(f)
            bakeries[bakery_name].secret_env = env

    app_config_path = get_app_config_path()
    with open(app_config_path) as c:
        kw = yaml.safe_load(c)
        if "sops" in kw:
            raise ValueError(f"Config file {app_config_path} is encrypted. Decrypt, then restart.")
        return Config(**kw, bakeries=bakeries)
