import fsspec
import yaml
from pydantic import ValidationError

from ..interfaces import PANGEO_FORGE_BAKERY_DATABASE
from ..meta_types.bakery import bakery_database_from_dict
from .exceptions import PangeoForgeValidationError


def open_bakery_database_yaml(path=None):
    path = path if path else PANGEO_FORGE_BAKERY_DATABASE
    with fsspec.open(path) as f:
        return yaml.safe_load(f.read())


def validate_bakery_database(path=None):
    d = open_bakery_database_yaml(path=path)
    try:
        bakery_database_from_dict(d)
    except ValidationError as e:
        raise PangeoForgeValidationError(str(e)) from e
