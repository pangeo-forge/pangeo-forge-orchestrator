from dataclasses import dataclass
from typing import List, Optional


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
    target_endpoint: str
    resources: Optional[Resources] = None


@dataclass
class Meta:
    title: str
    description: str
    pangeo_forge_version: str
    recipes: List[Recipe]
    bakery: RecipeBakery
    provenance: Optional[str]
    maintainers: Optional[str]
