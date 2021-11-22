import types
from dataclasses import dataclass
from typing import Optional, Union

from sqlmodel import Field, SQLModel


def make_cls_name(base: type, rename_base_to: str) -> str:
    """For a class name of format `"ClassBase"`, return a modified name in which
    the substring `"Base"` is replaced with the string passed to `rename_base_to`.

    :param base: The base model. It's name must end with the substring `"Base"`.
    :param rename_base_to: String to replace `"Base"` with.
    """
    return base.__name__.replace("Base", rename_base_to)


def make_creator_cls(base: SQLModel) -> SQLModel:
    """From a base model, make and return a creation model. As described in
    https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-herocreate-data-model,
    the creation model is simply a copy of the base model, with the substring `"Base"` in the
    class name replaced by the substring `"Create"`.

    :param base: The base model.
    """
    cls_name = make_cls_name(base, "Create")
    return type(cls_name, (base,), {})


def make_updater_cls(base: SQLModel) -> SQLModel:
    """From a base model, make and return an update model. As described in
    https://sqlmodel.tiangolo.com/tutorial/fastapi/update/#heroupdate-model, the update model
    is the same as the base model, but with all fields annotated as `Optional` and all field
    defaults set to `None`.

    :param base: The base model. Note that unlike in `make_creator`, this is not the base for
    inheritance (all updaters inherit directly from `SQLModel`) but rather is used to derive
    the output class name, attributes, and type annotations.
    """
    cls_name = make_cls_name(base, "Update")
    sig = base.__signature__
    params = list(sig.parameters)
    # Pulling type via `__signature__` rather than `__annotation__` because
    # this accessor drops the `typing.Union[...]` wrapper for optional fields
    annotations = {p: Union[sig.parameters[p].annotation, None] for p in params}
    defaults = {p: None for p in params}
    attrs = {**defaults, "__annotations__": annotations}
    return type(cls_name, (SQLModel,), attrs)


def make_table_cls(base: SQLModel) -> SQLModel:
    """From a base model, make and return a table model. As described in
    https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-hero-table-model,
    the table model is the same as the base model, with the addition of the `table=True` class
    creation keyword and an `id` attribute of type `Optional[int]` set to a default value of
    `Field(default=None, primary_key=True)`.

    :param base: The base model.
    """
    cls_name = make_cls_name(base, "")
    attrs = dict(id=Field(default=None, primary_key=True))
    annotations = dict(id=Union[int, None])
    attrs.update(dict(__annotations__=annotations))
    # We are using `typing.new_class` (vs. `type`) b/c it supports passing the `table=True` kwarg.
    # https://twitter.com/simonw/status/1430255521127305216?s=20
    # https://docs.python.org/3/reference/datamodel.html#customizing-class-creation
    return types.new_class(cls_name, (base,), dict(table=True), lambda ns: ns.update(attrs))


@dataclass
class MultipleModels:
    path: str
    table: SQLModel
    creation: SQLModel
    response: SQLModel
    update: SQLModel


# Specific model implementation -----------------------------------------------------------


class HeroBase(SQLModel):
    name: str
    secret_name: str
    age: Optional[int] = None


class HeroRead(HeroBase):
    id: int


Hero = make_table_cls(HeroBase)
HeroCreate = make_creator_cls(HeroBase)
HeroUpdate = make_updater_cls(HeroBase)

MODELS = {
    "hero": MultipleModels(
        path="/heroes/", table=Hero, creation=HeroCreate, response=HeroRead, update=HeroUpdate,
    )
}
