from typing import Optional

from sqlmodel import SQLModel

from .abstractions import MultipleModels


class HeroBase(SQLModel):
    name: str
    secret_name: str
    age: Optional[int] = None


class HeroRead(HeroBase):
    id: int


MODELS = {"hero": MultipleModels(path="/heroes/", base=HeroBase, response=HeroRead)}
