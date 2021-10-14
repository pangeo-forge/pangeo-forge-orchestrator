from dataclasses import dataclass


@dataclass
class Versions:
    pangeo_notebook_version: str
    pangeo_forge_version: str
    prefect_version: str
