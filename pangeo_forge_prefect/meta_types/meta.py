from dataclasses import dataclass
from typing import List, Literal, Optional


@dataclass
class Recipe:
    id: str
    module: str
    name: str


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
class Meta:
    title: str
    description: str
    pangeo_forge_version: str
    recipes: List[Recipe]
    bakery: RecipeBakery
    provenance: Optional[Provenance]
    maintainers: Optional[List[Maintainer]]
