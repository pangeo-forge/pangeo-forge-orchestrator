import json
from pathlib import Path

this_dir = Path(__file__).parent.resolve()
with open(this_dir / "secrets/osn.json") as f:
    creds = json.load(f)
    key = creds["key"]
    secret = creds["secret"]

    c.Deployment.dont_leak = [key, secret]  # type: ignore # noqa: F821

c.Deployment.name = "pangeo-forge"  # type: ignore # noqa: F821
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
                "key": key,
                "secret": secret,
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
