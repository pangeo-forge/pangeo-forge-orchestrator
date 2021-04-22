## Pangeo Forge Prefect
This module takes a Pangeo Forge recipe [meta.yaml](https://github.com/pangeo-forge/roadmap/blob/master/doc/adr/0002-use-meta-yaml-to-track-feedstock-metadata.md) and [bakeries.yaml](https://github.com/pangeo-forge/roadmap/blob/master/doc/adr/0004-use-yaml-file-for-bakery-database.md) and registers the `meta.yaml`'s recipes with Prefect Cloud using the its specified bakery information.

It is intended for use with Github Actions in the `pangeo-forge/staged-recipe` and `feedstock` repositories as outlined [here](https://github.com/pangeo-forge/roadmap/blob/master/doc/adr/0001-github-workflows.md).

## Requirements
The Python version used to serialize Flows must be the same as the worker images deployed in the bakery cluster.  Currently this requires Python 3.8.

In order to register flows with Prefect Cloud, the module requires the environment variable
```
PREFECT__CLOUD__AUTH_TOKEN
```
to be set to a [Prefect Service Account](https://docs.prefect.io/orchestration/concepts/tokens.html#service-account) key.

And the environment variable
```
PREFECT_PROJECT_NAME
```
To be set to the Pangeo Forge Prefect Cloud [project](https://docs.prefect.io/orchestration/concepts/projects.html#projects) name.

```
BUCKET_KEY
BUCKET_SECRET
```
Should be set to the values corresponding to the storage target from `bakeries.yaml`.

## Install
From source
```
$ pip install git+https://github.com/developmentseed/pangeo-forge-prefect.git
```

### Tests
```
$ tox
```

## Contributing
The use of a virtual environment is recommended.
### Dev install
```
$ git clone https://github.com/developmentseed/pangeo-forge-prefect
$ cd pangeo-forge-prefect
$ pip install -e .[dev]
```

This repo is set to use pre-commit to run isort, flake8, and black ("uncompromising Python code formatter") when committing new code.
```
$ pre-commit install
```
