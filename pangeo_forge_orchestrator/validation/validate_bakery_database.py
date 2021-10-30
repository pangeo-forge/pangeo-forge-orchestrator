from pydantic import ValidationError

from ..meta_types.bakery import BakeryDatabase
from .exceptions import PangeoForgeValidationError


def validate_bakery_database(path=None):
    kw = {} if not path else dict(path=path)
    try:
        BakeryDatabase(**kw)
    except ValidationError as e:
        raise PangeoForgeValidationError(str(e)) from e
