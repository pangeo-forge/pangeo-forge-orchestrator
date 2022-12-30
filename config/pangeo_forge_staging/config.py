# type: ignore

from pangeo_forge_orchestrator.configurables import get_default_container_image  # , open_secret

c.Deployment.name = "pangeo-forge-staging"

# TODO: complete this incomplete config (don't forget osn creds for runner config below)

c.Deployment.registered_runner_configs = {
    "pangeo-ldeo-nsf-earthcube": {
        "Bake": {"bakery_class": "pangeo_forge_runner.bakery.dataflow.DataflowBakery"},
        "DataflowBakery": {
            "temp_gcs_location": "gs://pangeo-forge-staging-dataflow/temp",
            "container_image": get_default_container_image(),
        },
        "TargetStorage": {
            "fsspec_class": "s3fs.S3FileSystem",
            "fsspec_args": {
                "client_kwargs": {"endpoint_url": "https://ncsa.osn.xsede.org"},
                "default_cache_type": "none",
                "default_fill_cache": False,
                "use_listings_cache": False,
            },
            "root_path": "Pangeo/{subpath}",
            "public_url": "https://ncsa.osn.xsede.org/{root_path}",
        },
        "InputCacheStorage": {
            "fsspec_class": "gcsfs.GCSFileSystem",
            "fsspec_args": {"bucket": "pangeo-forge-staging-cache"},
            "root_path": "pangeo-forge-staging-cache",
        },
        "MetadataCacheStorage": {
            "fsspec_class": "gcsfs.GCSFileSystem",
            "fsspec_args": {},
            "root_path": "pangeo-forge-staging-cache/metadata/{subpath}",
        },
    }
}
