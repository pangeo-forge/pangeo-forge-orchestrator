import types
from dataclasses import dataclass
from typing import List, Optional, Union

from sqlmodel import Field, Relationship, SQLModel


@dataclass
class RelationBuilder:
    """Data used to generate ``sqlmodel.Relationship``s in ``MultipleModels``. Based on:
    https://sqlmodel.tiangolo.com/tutorial/relationship-attributes/define-relationships-attributes/

    :param field: The name of the field to add to the table.
    :param annotation: The type annotation. If the relationship is one-to-one, the annotation will
    be a subclass of ``SQLModel`` corresponding to the table model for the related table. If the
    relationship is one-to-many, the annotation will be ``List[str]`` where ``str`` is the
    ``__name__`` of the related table model. In either case, type can be ``Optional``.
    :param back_populates: The name of the field in the related table to back populate. This field
      name must exist as a ``sqlmodel.Relationship`` attribute of the model referenced in the
      provided ``annotation``.
    """

    field: str
    annotation: Union[SQLModel, List[str]]
    back_populates: str


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
    :param extended_response: An optional response class for returning nested data from related
      tables in responses to ``read_single`` GET requests. For more information, refer to:
      https://sqlmodel.tiangolo.com/tutorial/fastapi/relationships/#models-with-relationships.
    :param relations: An optional list of ``RelationBuilder``s. If present, used to generate
       ``sqlmodel.Relationship`` attributes on the table class in ``self.make_table_cls``.
    """

    path: str
    base: SQLModel
    response: SQLModel
    descriptive_name: str
    extended_response: Optional[SQLModel] = None
    relations: Optional[List[RelationBuilder]] = None

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
        ``Field(default=None, primary_key=True)``. If ``self.relations`` are provided, they are
        defined on the table model as described in the SQLModel documentation:
        https://sqlmodel.tiangolo.com/tutorial/relationship-attributes/define-relationships-attributes/
        """
        cls_name = self.make_cls_name(self.base, "")
        attrs = dict(id=Field(default=None, primary_key=True))
        annotations = dict(id=Union[int, None])
        attrs |= dict(__annotations__=annotations)
        if self.relations:
            for r in self.relations:
                attrs[r.field] = Relationship(back_populates=r.back_populates)
                attrs.get("__annotations__").update({r.field: r.annotation})  # type: ignore
        # We are using `typing.new_class` (vs. `type`) b/c it supports the `table=True` kwarg.
        # https://twitter.com/simonw/status/1430255521127305216?s=20
        # https://docs.python.org/3/reference/datamodel.html#customizing-class-creation
        return types.new_class(
            cls_name, (self.base,), dict(table=True), lambda ns: ns.update(attrs)
        )
