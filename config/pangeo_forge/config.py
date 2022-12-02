from pathlib import Path

import yaml  # type: ignore
from traitlets.config import get_config

GCP_PROJECT = "pangeo-forge-4967"

root_dir = Path(__file__).parent.parent.parent.resolve()
this_dir = Path(__file__).parent.resolve()
secrets_dir = this_dir / "secrets"


def open_secrets(fname: str) -> dict:
    with open(secrets_dir / fname) as f:
        return yaml.safe_load(f)


fastapi = open_secrets("fastapi.yaml")
github_app = open_secrets("github-app.yaml")
osn_creds = open_secrets("osn.yaml")

c = get_config()

c.Deployment.dont_leak = [
    github_app["private_key"],
    github_app["webhook_secret"],
    fastapi["PANGEO_FORGE_API_KEY"],
    osn_creds["key"],
    osn_creds["secret"],
]

with open(root_dir / "dataflow-container-image.txt") as img_tag:
    container_image = f"gcr.io/{GCP_PROJECT}/{img_tag.read().strip()}"

c.Deployment.name = "pangeo-forge"

c.GitHubApp.app_name = github_app["app_name"]
c.GitHubApp.id = github_app["id"]
c.GitHubApp.private_key = github_app["private_key"]
c.GitHubApp.webhook_secret = github_app["webhook_secret"]

c.Deployment.fastapi = fastapi
c.Deployment.registered_runner_configs = {
    "pangeo-ldeo-nsf-earthcube": {
        "Bake": {
            "bakery_class": "pangeo_forge_runner.bakery.dataflow.DataflowBakery",
            "container_image": container_image,
        },
        "DataflowBakery": {
            "temp_gcs_location": "gs://pangeo-forge-prod-dataflow/temp",
        },
        "TargetStorage": {
            "fsspec_class": "s3fs.S3FileSystem",
            "fsspec_args": {
                "client_kwargs": {"endpoint_url": "https://ncsa.osn.xsede.org"},
                "default_cache_type": "none",
                "default_fill_cache": False,
                "use_listings_cache": False,
                "key": osn_creds["key"],
                "secret": osn_creds["secret"],
            },
            "root_path": "Pangeo/{subpath}",
            "public_url": "https://ncsa.osn.xsede.org/{root_path}",
        },
        "InputCacheStorage": {
            "fsspec_class": "gcsfs.GCSFileSystem",
            "fsspec_args": {
                "bucket": "pangeo-forge-prod-cache",
            },
            "root_path": "pangeo-forge-prod-cache",
        },
        "MetadataCacheStorage": {
            "fsspec_class": "gcsfs.GCSFileSystem",
            "fsspec_args": {},
            "root_path": "pangeo-forge-prod-cache/metadata/{subpath}",
        },
    },
}
