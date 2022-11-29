from pathlib import Path

import yaml  # type: ignore

this_dir = Path(__file__).parent.resolve()
secrets_dir = this_dir / "secrets"


def open_secrets(fname: str) -> dict:
    with open(secrets_dir / fname) as f:
        return yaml.safe_load(f)


fastapi = open_secrets("fastapi.yaml")
github_app = open_secrets("github-app.yaml")
osn_creds = open_secrets("osn.yaml")

c.Deployment.dont_leak = [  # type: ignore # noqa: F821
    github_app["private_key"],
    github_app["webhook_secret"],
    fastapi["PANGEO_FORGE_API_KEY"],
    osn_creds["key"],
    osn_creds["secret"],
]

c.Deployment.name = "pangeo-forge"  # type: ignore # noqa: F821
c.Deployment.github_app = github_app  # type: ignore # noqa: F821
c.Deployment.fastapi = fastapi  # type: ignore # noqa: F821
c.Deployment.registered_runner_configs = {  # type: ignore # noqa: F821
    "pangeo-ldeo-nsf-earthcube": {
        "Bake": {
            "bakery_class": "pangeo_forge_runner.bakery.dataflow.DataflowBakery",
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
