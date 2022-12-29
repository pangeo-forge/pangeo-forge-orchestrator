from traitlets.config import get_config  # fmt:skip isort:skip

# FIXME #####################################################################
# from .. import get_default_container_image, open_secret
#
# relative imports don't work, so copying helpers from ``..__init__.py`` here
import os
from pathlib import Path

import yaml  # type: ignore

root_dir = Path(__file__).parent.parent.parent.resolve()

DEFAULT_GCP_PROJECT = "pangeo-forge-4967"


def open_secret(fname: str) -> dict:
    with open(
        root_dir
        / "config"
        / os.environ["PANGEO_FORGE_DEPLOYMENT"].replace("-", "_")
        / "secrets"
        / fname
    ) as f:
        s = yaml.safe_load(f)
        if "sops" in s:
            raise ValueError(f"File {s} is encrypted. Decrypt then retry.")
        return s


def get_default_container_image():
    with open(root_dir / "dataflow-container-image.txt") as img_tag:
        return f"gcr.io/{DEFAULT_GCP_PROJECT}/{img_tag.read().strip()}"


# end FIXME #################################################################

c = get_config()

# could be set from os.environ, but maybe explicit is clearer?
c.Deployment.name = "pforge-pr-204"

fastapi = open_secret("fastapi.yaml")
c.FastAPI.key = fastapi["PANGEO_FORGE_API_KEY"]

github_app = open_secret("github-app.yaml")
c.GitHubApp.app_name = github_app["app_name"]
c.GitHubApp.id = github_app["id"]
c.GitHubApp.private_key = github_app["private_key"]
c.GitHubApp.webhook_secret = github_app["webhook_secret"]

# some of this is actually not secret, but this is most concise
# (and make sure there were no overlapping keys resulting in dropped values)
c.Deployment.dont_leak = [v for v in (fastapi | github_app).values()]
assert len(c.Deployment.dont_leak) == len(fastapi) + len(github_app)

c.SpawnerConfig.cls = "pangeo_forge_orchestrator.configurables.spawner.LocalSubprocessSpawner"
c.Deployment.registered_runner_configs = {
    "pangeo-ldeo-nsf-earthcube": {
        "Bake": {
            "bakery_class": "pangeo_forge_runner.bakery.dataflow.DataflowBakery",
            "container_image": get_default_container_image(),
        },
        "DataflowBakery": {"temp_gcs_location": "gs://pangeo-forge-dev-dataflow/temp"},
        "TargetStorage": {
            "fsspec_class": "gcsfs.GCSFileSystem",
            "fsspec_args": {"bucket": "pangeo-forge-dev-target"},
            "root_path": "pangeo-forge-dev-target/{subpath}",
            "public_url": "https://storage.googleapis.com/{root_path}",
        },
        "InputCacheStorage": {
            "fsspec_class": "gcsfs.GCSFileSystem",
            "fsspec_args": {"bucket": "pangeo-forge-dev-cache"},
            "root_path": "pangeo-forge-dev-cache",
        },
        "MetadataCacheStorage": {
            "fsspec_class": "gcsfs.GCSFileSystem",
            "fsspec_args": {},
            "root_path": "pangeo-forge-dev-cache/metadata/{subpath}",
        },
    }
}
