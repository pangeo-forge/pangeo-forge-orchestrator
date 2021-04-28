from setuptools import find_packages, setup

setup(
    name="pangeo_forge_prefect",
    packages=find_packages(),
    install_requires=[
        "pyyaml==5.4.1",
        "prefect==0.14.13",
        "botocore==1.19.52",
        "s3fs==0.6.0",
        "boto3==1.16.52",
        "dacite==1.6.0",
        "xarray@git+https://github.com/pydata/xarray",
        "dask-cloudprovider==2021.3.1",
        "rechunker@git+https://github.com/pangeo-data/rechunker#egg=rechunker",
        "pangeo_forge@git+https://github.com/pangeo-forge/pangeo-forge#egg=pangeo_forge",
    ],
    extras_require={
        "dev": ["flake8", "black", "pre-commit", "pre-commit-hooks", "isort", "pytest"],
        "test": ["flake8", "pytest"],
    },
)
