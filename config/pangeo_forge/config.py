from traitlets.config import get_config

from .. import get_default_container_image, open_secret

c = get_config()
c.Deployment.name = "pangeo-forge"

fastapi = open_secret("fastapi.yaml")
c.FastAPI.key = fastapi["PANGEO_FORGE_API_KEY"]

github_app = open_secret("github-app.yaml")
for k, v in github_app.items():
    setattr(c, "GitHubApp", v)

osn_creds = open_secret("osn.yaml")

# some of this is actually not secret, but this is most concise
c.Deployment.dont_leak = [v for v in (fastapi | github_app | osn_creds).values()]

c.Deployment.registered_runner_configs = {
    "pangeo-ldeo-nsf-earthcube": {
        "Bake": {
            "bakery_class": "pangeo_forge_runner.bakery.dataflow.DataflowBakery",
            "container_image": get_default_container_image(),
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
