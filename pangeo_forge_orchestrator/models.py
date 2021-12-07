from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel

from .abstractions import MultipleModels


class RecipeRunBase(SQLModel):
    recipe_id: str
    run_date: datetime
    bakery_id: int  # TODO: Foreign key
    feedstock_id: int  # TODO: Foreign key
    commit: str
    version: str
    status: str  # TODO: Enum or categorical
    path: str  # Deterministic if in spec, but existing catalog not all in spec.
    message: Optional[str] = None


class RecipeRunRead(RecipeRunBase):
    id: int


MODELS = {
    "recipe_run": MultipleModels(path="/recipe_runs/", base=RecipeRunBase, response=RecipeRunRead)
}
