import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel


class FastAPIConfig(BaseModel):
    ADMIN_API_KEY_SHA256: str
    ENCRYPTION_SALT: str
    PANGEO_FORGE_API_KEY: str


class GitHubAppConfig(BaseModel):
    id: int
    webhook_url: str
    webhook_secret: str
    private_key: str
    run_only_on: Optional[List[str]] = None


class Config(BaseModel):
    fastapi: FastAPIConfig
    github_app: GitHubAppConfig


def get_config_path() -> str:
    # Named Heroku deployments set the PANGEO_FORGE_DEPLOYMENT env variable: for production, this
    # is `prod`; for staging, it's `staging`. Therefore, in a named deployment context, config
    # filenames will resolve to `github_app_config.prod.yaml` and `github_app_config.staging.yaml`,
    # respectively. If PANGEO_FORGE_DEPLOYMENT is unset, assume we're in a dev environment.
    deployment = os.environ.get("PANGEO_FORGE_DEPLOYMENT", "dev")
    # The pre-commit-hook-ensure-sops hook installed in this repo's .pre-commit-config.yaml will
    # prevent commiting unencyrpted secrets to this directory.
    secrets_dir = f"{Path(__file__).resolve().parent.parent}/secrets"
    config_path = f"{secrets_dir}/config.{deployment}.yaml"
    return config_path


def get_config() -> Config:
    config_path = get_config_path()
    with open(config_path) as c:
        kw = yaml.safe_load(c)
        return Config(**kw)
