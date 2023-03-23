from inspect import signature
from typing import Callable

returns = {
    "recipe_pr": dict,
}


def assert_fixture_returns(f: Callable) -> Callable:
    """Decorator to ensure that fixtures have the required signature."""

    fixture_returns = signature(f).return_annotation
    required_returns = returns[f.__name__]

    if fixture_returns == required_returns:
        raise ValueError(
            f"Fixture '{f.__name__}' with {fixture_returns = } does not "
            f"match {required_returns = }"
        )
    return f
