from pathlib import Path

import yaml  # type: ignore

this_dir = Path(__file__).parent.resolve()
secrets_dir = this_dir / "secrets"

with open(secrets_dir / "github-app.yaml") as f:
    github_app = yaml.safe_load(f)

with open(secrets_dir / "osn.yaml") as f:
    osn_creds = yaml.safe_load(f)

c.Deployment.dont_leak = [  # type: ignore # noqa: F821
    github_app["private_key"],
    github_app["webhook_secret"],
    osn_creds["key"],
    osn_creds["secret"],
]

c.Deployment.name = "pangeo-forge"  # type: ignore # noqa: F821
c.Deployment.github_app = github_app  # type: ignore # noqa: F821
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
