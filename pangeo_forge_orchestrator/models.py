from typing import Optional

from sqlmodel import Field, SQLModel


class HeroBase(SQLModel):
    name: str
    secret_name: str
    age: Optional[int] = None


class Hero(HeroBase, table=True):  # type: ignore
    # `error: Unexpected keyword argument "table" for "__init_subclass__" of "object"  [call-arg]`
    # mypy inheritance issue, similar to https://github.com/python/mypy/issues/10021
    id: Optional[int] = Field(default=None, primary_key=True)


class HeroCreate(HeroBase):
    pass


class HeroRead(HeroBase):
    id: int


class HeroUpdate(SQLModel):
    name: Optional[str] = None
    secret_name: Optional[str] = None
    age: Optional[int] = None
