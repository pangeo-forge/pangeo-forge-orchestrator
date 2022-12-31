import json
import os
from pathlib import Path

import yaml  # type: ignore
from traitlets import Type
from traitlets.config import Application, Configurable

from .deployment import Deployment  # noqa: F401
from .fastapi import FastAPI  # noqa: F401
from .github_app import GitHubApp  # noqa: F401
from .spawner import SpawnerABC, SpawnerConfig  # noqa: F401

ROOT = Path(__file__).parent.parent.parent.resolve()


def get_default_container_image(gcp_project):
    with open(ROOT / "dataflow-container-image.txt") as img_tag:
        return f"gcr.io/{gcp_project}/{img_tag.read().strip()}"


def get_config_dir() -> Path:
    passed_explicitly = os.environ.get("ORCHESTRATOR_CONFIG_DIR", None)
    if not passed_explicitly:
        deployment_name = os.environ.get("PANGEO_FORGE_DEPLOYMENT", None)
        if not deployment_name:
            raise ValueError(
                "Either ORCHESTRATOR_CONFIG_DIR or PANGEO_FORGE_DEPLOYMENT env var must be set. "
                "Use ORCHESTRATOR_CONFIG_DIR to pass an absolute path to a config dir. Or use "
                "PANGEO_FORGE_DEPLOYMENT to indicate that a config file exists at the relative "
                "path './{REPO_ROOT}/config/{PANGEO_FORGE_DEPLOYMENT.replace('-', '_')}/config.py'."
            )
        generated = ROOT / "config" / deployment_name.replace("-", "_")
    return Path(passed_explicitly) if passed_explicitly else generated


def get_config_file() -> Path:
    config_file = get_config_dir() / "config.py"
    if not os.path.exists(config_file):
        raise ValueError(f"{config_file = } does not exist.")
    return config_file


def get_secrets_dir() -> Path:
    return get_config_dir() / "secrets"


class EncryptedSecretError(ValueError):
    pass


def open_secret(fname: str) -> dict:
    with open(get_secrets_dir() / fname) as f:
        _, ext = os.path.splitext(fname)
        if ext in (".yaml", ".yml"):
            s = yaml.safe_load(f)
        elif ext == ".json":
            s = json.load(f)
        else:
            raise ValueError(f"{fname} extension {ext} not in ['.yaml', '.yml', '.json']")
        if "sops" in s:
            raise EncryptedSecretError(f"File '{fname}' is encrypted. Decrypt then retry.")
        return s


def check_secrets_decrypted() -> None:
    sd = get_secrets_dir()
    if os.path.exists(sd):
        errors = []
        for fname in os.listdir(sd):
            try:
                _ = open_secret(fname)
            except EncryptedSecretError as e:
                errors.append(e)
        if errors:
            raise EncryptedSecretError(errors)


class _GetConfigurable(Application):
    # FIXME: We don't actually run a traitlets Application here. We just need this context to
    # resolve traitlets config. Is there a more idiomatic way of doing this?

    configurable = Type(
        klass=Configurable,
        allow_none=False,
    )

    def initialize(self):
        config_file = get_config_file()
        self.load_config_file(config_file)

    def resolve(self):
        # FIXME: It seems like we should be able to avoid calling initialize every time by
        # checking ``if not self.initialized():``. However, in certain contexts this causes
        # problems by resulting in an empty config that still believes itself to be "intialized".
        # So to avoid that problem for now, just calling initialize on every resolution works.
        self.initialize()
        return self.configurable(parent=self)


def get_configurable(configurable: Configurable) -> Configurable:
    """Convenience function to resolve global app config outside of ``traitlets`` object."""
    return _GetConfigurable(configurable=configurable).resolve()


def get_spawner() -> SpawnerABC:
    s: SpawnerConfig = _GetConfigurable(configurable=SpawnerConfig).resolve()
    return s.cls(**s.kws)
