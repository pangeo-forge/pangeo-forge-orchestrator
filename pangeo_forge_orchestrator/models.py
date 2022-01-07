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
    """A container used to hold the responses to GET requests to the API; a.k.a. a "response
    model". As defined in the SQLModel docs linked below, "This ... declares that the id field is
    required when reading a [table] from the API, because a [table] read from the API will come
    from the database, and in the database it will always have an ID." For more, see:
    https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-heroread-data-model. (Note
    that "id" is just another way of saying "primary key".)
    """

    id: int


MODELS = {
    "recipe_run": MultipleModels(path="/recipe_runs/", base=RecipeRunBase, response=RecipeRunRead)
}
