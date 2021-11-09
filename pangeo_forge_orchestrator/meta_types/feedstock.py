from typing import List, Literal, Optional

from pydantic.dataclasses import dataclass


@dataclass
class Recipe:
    id: Optional[str] = None
    object: Optional[str] = None
    dict_object: Optional[str] = None

    def __post_init__(self):
        if self.id is None and self.dict_object is None:
            raise TypeError("Value needed for either id or dict_object")


@dataclass
class Resources:
    memory: int
    cpu: int


@dataclass
class RecipeBakery:
    id: str
    target: str
    resources: Optional[Resources] = None


@dataclass
class Provider:
    name: str
    description: str
    roles: List[Literal["producer", "licensor"]]
    url: str


@dataclass
class Provenance:
    providers: List[Provider]
    license: str


@dataclass
class Maintainer:
    name: str
    orcid: Optional[str]
    github: Optional[str]


@dataclass
class MetaDotYaml:
    title: str
    description: str
    pangeo_forge_version: str
    pangeo_notebook_version: str
    recipes: List[Recipe]
    bakery: RecipeBakery
    provenance: Optional[Provenance]
    maintainers: Optional[List[Maintainer]]
