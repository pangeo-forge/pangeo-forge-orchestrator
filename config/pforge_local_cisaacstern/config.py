# type: ignore

from pangeo_forge_orchestrator.configurables import get_default_container_image  # , open_secret

c.Deployment.name = "pforge-local-cisaacstern"

# TODO: complete this incomplete config

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
