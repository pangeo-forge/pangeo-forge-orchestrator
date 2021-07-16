from setuptools import find_packages, setup

setup(
    name="pangeo_forge_prefect",
    packages=find_packages(),
    install_requires=[
        "pangeo-forge-recipes>=0.4.0",
        "pyyaml==5.4.1",
        "prefect[aws]>=0.14.13",
        "dacite==1.6.0",
        "dask-cloudprovider[aws]>=2021.3.0",
        "dask-kubernetes>=2021.3.1",
        "s3fs>=0.6.0",
        "adlfs>=0.7.5",
    ],
    extras_require={
        "dev": ["flake8", "black", "pre-commit", "pre-commit-hooks", "isort", "pytest"],
        "test": ["flake8", "pytest"],
    },
)
