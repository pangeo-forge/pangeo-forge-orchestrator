import os
from pathlib import Path

import yaml  # type: ignore

root_dir = Path(__file__).parent.parent.resolve()

DEFAULT_GCP_PROJECT = "pangeo-forge-4967"


def open_secret(fname: str) -> dict:
    with open(
        root_dir
        / "config"
        / os.environ["PANGEO_FORGE_DEPLOYMENT"].replace("-", "_")
        / "secrets"
        / fname
    ) as f:
        return yaml.safe_load(f)


def get_default_container_image():
    with open(root_dir / "dataflow-container-image.txt") as img_tag:
        return f"gcr.io/{DEFAULT_GCP_PROJECT}/{img_tag.read().strip()}"
