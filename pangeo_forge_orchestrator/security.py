import hmac

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from starlette import status

from .config import get_fastapi_config

X_API_KEY = APIKeyHeader(name="X-API-Key")


def check_authentication_header(x_api_key: str = Depends(X_API_KEY)) -> bool:
    """Takes the X-API-Key header and securely compares it to the current api key."""

    if hmac.compare_digest(x_api_key, get_fastapi_config().PANGEO_FORGE_API_KEY):
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )
