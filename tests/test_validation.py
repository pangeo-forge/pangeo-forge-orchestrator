import pytest

from pangeo_forge_orchestrator.validation import (
    PangeoForgeValidationError,
    validate_bakery_database,
)


@pytest.mark.parametrize("invalid", [None, "http_path", "content"])
def test_bakery_database_validation(invalid, github_http_server):
    bakery_database_http_path = github_http_server[-1]
    if not invalid:
        validate_bakery_database(path=bakery_database_http_path)
    elif invalid == "http_path":
        path = bakery_database_http_path.replace("://", "")
        with pytest.raises(PangeoForgeValidationError):
            validate_bakery_database(path=path)
    elif invalid == "content":
        with pytest.raises(PangeoForgeValidationError):
            validate_bakery_database()
