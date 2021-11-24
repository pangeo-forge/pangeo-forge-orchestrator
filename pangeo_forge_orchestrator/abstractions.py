import types
from dataclasses import dataclass
from typing import Callable, List, Union

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, select

# Model generator + container -------------------------------------------------------------


@dataclass
class MultipleModels:
    path: str
    base: SQLModel
    response: SQLModel

    def __post_init__(self):
        self.creation: SQLModel = self.make_creator_cls()
        self.table: SQLModel = self.make_table_cls()
        self.update: SQLModel = self.make_updater_cls()

    @staticmethod
    def make_cls_name(base: type, rename_base_to: str) -> str:
        """For a class name of format ``"ClassBase"``, return a modified name in which
        the substring ``"Base"`` is replaced with the string passed to ``rename_base_to``.
        :param base: The base model. It's name must end with the substring ``"Base"``.
        :param rename_base_to: String to replace `"Base"` with.
        """
        return base.__name__.replace("Base", rename_base_to)

    def make_creator_cls(self) -> SQLModel:
        """From a base model, make and return a creation model. As described in
        https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-herocreate-data-model,
        the creation model is simply a copy of the base model, with the substring ``"Base"`` in the
        class name replaced by the substring ``"Create"``.
        :param base: The base model.
        """
        cls_name = self.make_cls_name(self.base, "Create")
        return type(cls_name, (self.base,), {})

    def make_updater_cls(self) -> SQLModel:
        """From a base model, make and return an update model. As described in
        https://sqlmodel.tiangolo.com/tutorial/fastapi/update/#heroupdate-model, the update model
        is the same as the base model, but with all fields annotated as ``Optional`` and all field
        defaults set to ``None``.
        :param base: The base model. Note that unlike in ``make_creator``, this is not the base for
        inheritance (all updaters inherit directly from ``SQLModel``) but rather is used to derive
        the output class name, attributes, and type annotations.
        """
        cls_name = self.make_cls_name(self.base, "Update")
        sig = self.base.__signature__
        params = list(sig.parameters)
        # Pulling type via `__signature__` rather than `__annotation__` because
        # this accessor drops the `typing.Union[...]` wrapper for optional fields
        annotations = {p: Union[sig.parameters[p].annotation, None] for p in params}
        defaults = {p: None for p in params}
        attrs = {**defaults, "__annotations__": annotations}
        return type(cls_name, (SQLModel,), attrs)

    def make_table_cls(self) -> SQLModel:
        """From a base model, make and return a table model. As described in
        https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-hero-table-model,
        the table model is the same as the base model, with the addition of the ``table=True`` class
        creation keyword and an ``id`` attribute of type ``Optional[int]`` set to a default value of
        ``Field(default=None, primary_key=True)``.
        :param base: The base model.
        """
        cls_name = self.make_cls_name(self.base, "")
        attrs = dict(id=Field(default=None, primary_key=True))
        annotations = dict(id=Union[int, None])
        attrs.update(dict(__annotations__=annotations))
        # We are using `typing.new_class` (vs. `type`) b/c it supports the `table=True` kwarg.
        # https://twitter.com/simonw/status/1430255521127305216?s=20
        # https://docs.python.org/3/reference/datamodel.html#customizing-class-creation
        return types.new_class(
            cls_name, (self.base,), dict(table=True), lambda ns: ns.update(attrs)
        )


# SQLModel database interface functions ---------------------------------------------------


def create(*, session: Session, table_cls: SQLModel, model: SQLModel) -> SQLModel:
    db_model = table_cls.from_orm(model)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


def read_range(*, session: Session, table_cls: SQLModel, offset: int, limit: int) -> List:
    return session.exec(select(table_cls).offset(offset).limit(limit)).all()


def read_single(*, session: Session, table_cls: SQLModel, id: int):
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    return db_model


def update(*, session: Session, table_cls: SQLModel, id: int, model: SQLModel) -> SQLModel:
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    model_data = model.dict(exclude_unset=True)
    for key, value in model_data.items():
        setattr(db_model, key, value)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


def delete(*, session: Session, table_cls: SQLModel, id: int) -> dict:
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    session.delete(db_model)
    session.commit()
    return {"ok": True}


# Endpoint registration -------------------------------------------------------------------


@dataclass
class RegisterEndpoints:
    """From a ``MultipleModels`` object, register create, read, update, delete (CRUD) API endpoints.

    :param api: The ``FastAPI`` instance.
    :param get_session: A function which yields a context-managed ``sqlmodel.Session`` object.
    :param models: The ``MultipleModels`` object.
    :param limit: The bounds for an API read requests.
    """

    api: FastAPI
    get_session: Callable
    models: MultipleModels
    limit: Query = Query(default=100, lte=100)

    def __post_init__(self):
        self.register_all()

    def register_all(self):
        self.register_create_endpoint()
        self.register_read_range_endpoint()
        self.register_read_single_endpoint()
        self.register_update_endpoint()
        self.register_delete_endpoint()

    def register_create_endpoint(self):
        @self.api.post(self.models.path, response_model=self.models.response)
        def endpoint(
            *,
            session: Session = Depends(self.get_session),
            model: self.models.creation,  # type: ignore
        ):
            return create(session=session, table_cls=self.models.table, model=model)

    def register_read_range_endpoint(self):
        @self.api.get(self.models.path, response_model=List[self.models.response])
        def endpoint(
            *,
            session: Session = Depends(self.get_session),
            offset: int = 0,
            limit: int = self.limit,
        ):
            return read_range(
                session=session, table_cls=self.models.table, offset=offset, limit=limit,
            )

    def register_read_single_endpoint(self):
        @self.api.get(self.models.path + "{id}", response_model=self.models.response)
        def endpoint(*, session: Session = Depends(self.get_session), id: int):
            return read_single(session=session, table_cls=self.models.table, id=id)

    def register_update_endpoint(self):
        @self.api.patch(self.models.path + "{id}", response_model=self.models.response)
        def endpoint(
            *,
            session: Session = Depends(self.get_session),
            id: int,
            model: self.models.update,  # type: ignore
        ):
            return update(session=session, table_cls=self.models.table, id=id, model=model)

    def register_delete_endpoint(self):
        @self.api.delete(self.models.path + "{id}")
        def endpoint(*, session: Session = Depends(self.get_session), id: int):
            return delete(session=session, table_cls=self.models.table, id=id)


def register_endpoints(
    api: FastAPI,
    get_session: Callable,
    models: MultipleModels,
    limit: Query = Query(default=100, lte=100),
):
    _ = RegisterEndpoints(api, get_session, models, limit)
