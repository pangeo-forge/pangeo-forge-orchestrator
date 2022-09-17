import os
from pathlib import Path
from typing import Dict, List

import yaml
from pydantic import BaseModel


class FastAPIConfig(BaseModel):
    ADMIN_API_KEY_SHA256: str
    ENCRYPTION_SALT: str
    PANGEO_FORGE_API_KEY: str


class GitHubAppConfig(BaseModel):
    id: int
    app_name: str
    webhook_secret: str
    private_key: str


class Bakeries(BaseModel):
    compute: Dict[str, List[Path]]
    storage: Dict[str, List[Path]]


root = Path(__file__).resolve().parent.parent
secrets_dir = root / "secrets"


def get_app_config_path() -> Path:
    deployment = os.environ.get("PANGEO_FORGE_DEPLOYMENT")
    if not deployment:
        raise ValueError("Env var PANGEO_FORGE_DEPLOYMENT must be set, but is not.")
    return secrets_dir / f"config.{deployment}.yaml"


def load_yaml_secrets(path: Path) -> dict:
    with open(path) as c:
        kw = yaml.safe_load(c)
        if "sops" in kw:
            raise ValueError(f"File {path} is encrypted. Decrypt, then restart.")
        return kw


def get_fastapi_config() -> FastAPIConfig:
    path = get_app_config_path()
    kw = load_yaml_secrets(path)
    return FastAPIConfig(**kw["fastapi"])


def get_github_app_config() -> GitHubAppConfig:
    path = get_app_config_path()
    kw = load_yaml_secrets(path)
    return GitHubAppConfig(**kw["github_app"])


def get_bakeries() -> Bakeries:
    def compile_config(src: Path) -> Dict[str, List[Path]]:
        config = {os.path.splitext(p)[0]: [src / p] for p in os.listdir(src)}
        secrets = {
            os.path.splitext(p)[0]: secrets_dir / p
            for p in os.listdir(secrets_dir)
            if os.path.splitext(p)[0] in config
        }
        for k in secrets:
            _ = load_yaml_secrets(secrets[k])
            config[k].append(secrets[k])
        return config

    return Bakeries(
        compute=compile_config(root / "bakeries" / "compute"),
        storage=compile_config(root / "bakeries" / "storage"),
    )
