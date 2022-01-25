import types
from dataclasses import dataclass
from typing import Callable, List, Union

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, select

QUERY_LIMIT = Query(default=100, lte=100)


# Model generator + container -------------------------------------------------------------


@dataclass
class MultipleModels:
    """For any given API endpoint, a distinct Python object is required to manage each of type of
    interaction that a user has with the database. Typically, these interaction types will be one
    of the create, read, update, and delete (CRUD) operations. Rather than writing a distinct class
    for each of these four interaction types, ``SQLModel``'s multiple models with inheritance
    (https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#multiple-models-with-inheritance)
    design pattern allows us to use Python class inheritance to avoid repetition. In this style,
    we define a base model from which all other models can be deterministically derived. This
    class, ``MultipleModels``, provides a container for generating and holding a grouping of these
    objects, and is used to implement ``SQLModel``'s multiple models with inheritance design pattern
    more reliably and with less code repetition than is currently supported by ``SQLModel`` alone.

    :param path: The relative path (a.k.a. route or endpoint) of the API which the objects contained
      in this class will be used to interact with. For example, ``"/my_database_table/"``.
    :param base: The base model. This object must inherit from ``sqlmodel.SQLModel`` and contain
      type-annotated fields for each of the columns in the database table. Its name must be of
      the format ``<TableName>Base``.
    :param response: The response class. This object inherits from the base model and defines just
      one additional required field, ``id``, with type ``int``. Its name must be of the format
      ``<TableName>Read``. Note that while this object can theoretically be deterministically
      generated from the base model, in practical terms it is difficult to succinctly generate with
      either Python's built-in ``type()`` or ``types.new_class()`` function, therefore the most
      robust option is simply for the user to define and pass it to ``MultipleModels`` manually.
      (Note also that "id" as used here is just another way of saying "primary key".)
    """

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
        """
        cls_name = self.make_cls_name(self.base, "Create")
        return type(cls_name, (self.base,), {})

    def make_updater_cls(self) -> SQLModel:
        """From a base model, make and return an update model. As described in
        https://sqlmodel.tiangolo.com/tutorial/fastapi/update/#heroupdate-model, the update model
        is the same as the base model, but with all fields annotated as ``Optional`` and all field
        defaults set to ``None``. Note that unlike in ``make_creator``, the class returned from this
        method does not inherit from the base model, but rather inherits directly from ``SQLModel``.
        In this method, the base model is used to derive the returned class's name, attributes, and
        type annotations.
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
    """Create an entry in the database with ``SQLModel``.

    :param session: A ``sqlmodel.Session`` object connected to the database.
    :param table_cls: An uninstantiated table model as described in
      https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-hero-table-model.
      If using a ``MultipleModels`` container, this is accessed via the ``.table`` attribute of
      the ``MultipleModels`` instance.
    :param model: The instantied table model to add to the database. If using a ``MultipleModels``
      container, this is created by passing the desired kwargs to ``.table`` attribute of the
      ``MultipleModels`` instance.
    """
    db_model = table_cls.from_orm(model)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


def read_range(*, session: Session, table_cls: SQLModel, offset: int, limit: int) -> List:
    """Read all entries within a range for in a given database table with ``SQLModel``.

    :param session: A ``sqlmodel.Session`` object connected to the database.
    :param table_cls: An uninstantiated table model as described in
      https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-hero-table-model.
      If using a ``MultipleModels`` container, this is accessed via the ``.table`` attribute of
      the ``MultipleModels`` instance.
    :param offset: The integer offset from which to begin the read. ``offset=0`` will start from
      the beginning of the table.
    :param limit: The maximum number of entries to read. Useful for tables with large numbers of
      entries to avoid returning unmanageably large lists. If your table doesn't have many entries,
      and you'd like to read them all, you can pass ``limit=<INT>`` where ``<INT>`` is any integer
      larger than the number of entries in your table.
    """
    return session.exec(select(table_cls).offset(offset).limit(limit)).all()


def read_single(*, session: Session, table_cls: SQLModel, id: int):
    """Read a single entry from the database with ``SQLModel``.

    :param session: A ``sqlmodel.Session`` object connected to the database.
    :param table_cls: An uninstantiated table model as described in
      https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-hero-table-model.
      If using a ``MultipleModels`` container, this is accessed via the ``.table`` attribute of
      the ``MultipleModels`` instance.
    :param id: The integer id (a.k.a. primary key) of the entry to read.
    """
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    return db_model


def update(*, session: Session, table_cls: SQLModel, id: int, model: SQLModel) -> SQLModel:
    """Update a database entry using ``SQLModel``.

    :param session: A ``sqlmodel.Session`` object connected to the database.
    :param table_cls: An uninstantiated table model as described in
      https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-hero-table-model.
      If using a ``MultipleModels`` container, this is accessed via the ``.table`` attribute of
      the ``MultipleModels`` instance.
    :param id: The integer id (a.k.a. primary key) of the entry to update.
    :param model: The instantied update model to use for update. If using a ``MultipleModels``
      container, this is created by passing any fields to update as kwargs to the ``.update``
      attribute of the ``MultipleModels`` instance.
    """
    db_model = session.get(table_cls, id)
    if not db_model:
        # TODO: add test coverage for this
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    model_data = model.dict(exclude_unset=True)
    for key, value in model_data.items():
        setattr(db_model, key, value)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


def delete(*, session: Session, table_cls: SQLModel, id: int) -> dict:
    """Delete a model in the database with ``SQLModel``.

    param session: A ``sqlmodel.Session`` object connected to the database.
    :param table_cls: An uninstantiated table model as described in
      https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-hero-table-model.
      If using a ``MultipleModels`` container, this is accessed via the ``.table`` attribute of
      the ``MultipleModels`` instance.
    :param id: The integer id (a.k.a. primary key) of the entry to delete.
    """
    db_model = session.get(table_cls, id)
    if not db_model:
        raise HTTPException(status_code=404, detail=f"{table_cls.__name__} not found")
    session.delete(db_model)
    session.commit()
    return {"ok": True}


# Endpoint registration -------------------------------------------------------------------


@dataclass
class _RegisterEndpoints:
    """From a ``MultipleModels`` object, register create, read, update, delete (CRUD) API endpoints.

    :param api: The ``FastAPI`` instance.
    :param get_session: A function which yields a context-managed ``sqlmodel.Session`` object.
    :param models: The ``MultipleModels`` object.
    :param limit: The bounds for an API read requests.
    """

    api: FastAPI
    get_session: Callable
    models: MultipleModels
    auth_dependency: Callable
    limit: Query = QUERY_LIMIT

    def __post_init__(self):
        # register all endpoints
        self.register_create_endpoint()
        self.register_read_range_endpoint()
        self.register_read_single_endpoint()
        self.register_update_endpoint()
        self.register_delete_endpoint()

    def register_create_endpoint(self):
        @self.api.post(self.models.path, response_model=self.models.response)
        def _create(
            *,
            session: Session = Depends(self.get_session),
            model: self.models.creation,  # type: ignore
            authorized_user=Depends(self.auth_dependency),
        ):
            return create(session=session, table_cls=self.models.table, model=model)

    def register_read_range_endpoint(self):
        @self.api.get(self.models.path, response_model=List[self.models.response])
        def _read_range(
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
        def _read_single(*, session: Session = Depends(self.get_session), id: int):
            return read_single(session=session, table_cls=self.models.table, id=id)

    def register_update_endpoint(self):
        @self.api.patch(self.models.path + "{id}", response_model=self.models.response)
        def _update(
            *,
            session: Session = Depends(self.get_session),
            id: int,
            model: self.models.update,  # type: ignore
            authorized_user=Depends(self.auth_dependency),
        ):
            return update(session=session, table_cls=self.models.table, id=id, model=model)

    def register_delete_endpoint(self):
        @self.api.delete(self.models.path + "{id}")
        def _delete(
            *,
            session: Session = Depends(self.get_session),
            id: int,
            authorized_user=Depends(self.auth_dependency),
        ):
            return delete(session=session, table_cls=self.models.table, id=id)


def register_endpoints(
    api: FastAPI,
    get_session: Callable,
    models: MultipleModels,
    auth_dependency: Callable,
    limit: Query = QUERY_LIMIT,
):
    _RegisterEndpoints(
        api=api,
        get_session=get_session,
        models=models,
        auth_dependency=auth_dependency,
        limit=limit,
    )
