import json
import os
from pathlib import Path
from typing import Optional

import yaml  # type: ignore
from pydantic import BaseModel, Extra, Field, SecretStr

GCP_PROJECT = "pangeo-forge-4967"
root = Path(__file__).resolve().parent.parent


class GitHubAppConfig(BaseModel):
    id: int
    app_name: str
    webhook_secret: str
    private_key: str
    run_only_on: Optional[list[str]] = None


def get_gcr_container_image_url():
    with open(root / "dataflow-container-image.txt") as img_tag:
        return f"gcr.io/{GCP_PROJECT}/{img_tag.read().strip()}"


class Bake(BaseModel):
    bakery_class: str
    job_name: Optional[str]
    container_image: str = Field(default_factory=get_gcr_container_image_url)


class FsspecArgs(BaseModel):
    # Universal container for all fsspec filesystem types. All fields are optional, so
    # any combination could theoretically be passed, but they are grouped according to
    # the filesystem they should be used with.

    # GCSFileSystem
    bucket: Optional[str]

    # S3FileSystem
    client_kwargs: Optional[dict]
    default_cache_type: Optional[str]
    default_fill_cache: Optional[bool]
    use_listings_cache: Optional[bool]
    key: Optional[SecretStr]
    secret: Optional[SecretStr]

    class Config:
        # Extras are forbidden here (see `Config` attribute) because this model might contain
        # secrets. Any secret values should have type `Optional[SecretStr]` so they are not
        # accidentally printed to the logs. If we don't forbid extras, some secrets might be
        # passed into this model, without being parsed to `SecretStr`.
        extra = Extra.forbid
        # Only allow resolution of secret values via `.json()`, all other methods conceal values.
        # https://pydantic-docs.helpmanual.io/usage/types/#secret-types
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value() if v else None,
        }


class Storage(BaseModel):
    fsspec_class: str
    fsspec_args: FsspecArgs
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

    def export_with_secrets(self):
        d = self.dict()
        # `FsspecArgs` might contain secrets, which cannot be resolved unless the `.json()`
        # method is called on `FsspecArgs` directly. This is good! It prevents us from
        # leaking secrets to logs, even if `Bakery.json()` is called. The only way to get
        # the full config, including secrets, it to call `Bakery.export_with_secrets()`.

        d["TargetStorage"]["fsspec_args"] = json.loads(
            self.TargetStorage.fsspec_args.json(exclude_none=True)
        )
        d["InputCacheStorage"]["fsspec_args"] = json.loads(
            self.InputCacheStorage.fsspec_args.json(exclude_none=True)
        )
        d["MetadataCacheStorage"]["fsspec_args"] = json.loads(
            self.MetadataCacheStorage.fsspec_args.json(exclude_none=True)
        )
        return d


class Config(BaseModel):
    github_app: GitHubAppConfig
    bakeries: dict[str, Bakery]


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


def get_app_config_kws() -> dict:
    app_config_path = get_app_config_path()
    with open(app_config_path) as c:
        kw = yaml.safe_load(c)
        if "sops" in kw:
            raise ValueError(f"Config file {app_config_path} is encrypted. Decrypt, then restart.")
        return kw


def get_bakeries_dir():
    return f"{root}/bakeries"


def get_secrets_dir():
    return f"{root}/secrets"


def get_secret_bakery_args_paths() -> list[str]:
    return [p for p in os.listdir(get_secrets_dir()) if p.startswith("bakery-args")]


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

    kw = get_app_config_kws()
    bakeries_dir = get_bakeries_dir()
    bakery_config_paths = [
        p
        for p in os.listdir(bakeries_dir)
        if p.split(".")[1] == os.environ.get("PANGEO_FORGE_DEPLOYMENT")
    ]
    bakery_kws = {}
    for p in bakery_config_paths:
        with open(f"{bakeries_dir}/{p}") as f:
            bakery_kws[p.split(".")[0]] = yaml.safe_load(f)

    for p in get_secret_bakery_args_paths():
        bakery_name = p.split(".")[1]
        this_bakery = bakery_kws[bakery_name]
        with open(f"{get_secrets_dir()}/{p}") as f:
            bakery_secret_args = yaml.safe_load(f)
            for storage_type in list(bakery_secret_args):
                # assumes secrets are only for storage,
                # all storage types have "fsspec_args"
                existing_args = this_bakery[storage_type]["fsspec_args"]
                additional_args = bakery_secret_args[storage_type]["fsspec_args"]
                existing_args.update(additional_args)

    bakeries = {k: Bakery(**v) for k, v in bakery_kws.items()}

    return Config(**kw, bakeries=bakeries)
