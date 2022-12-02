import hmac

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from starlette import status

from .configurables import FastAPI, get_configurable

X_API_KEY = APIKeyHeader(name="X-API-Key")


def check_authentication_header(x_api_key: str = Depends(X_API_KEY)) -> bool:
    """Takes the X-API-Key header and securely compares it to the current api key."""

    if hmac.compare_digest(x_api_key, get_configurable(configurable=FastAPI).key):
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )
