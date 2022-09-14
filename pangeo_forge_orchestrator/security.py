import hashlib
from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from starlette import status

from .config import get_fastapi_config
from .database import get_session
from .models import APIKey, APIKeyRead

X_API_KEY = APIKeyHeader(name="X-API-Key")


def get_salt() -> str:
    return get_fastapi_config().ENCRYPTION_SALT


def encrypt(value: str) -> str:
    salt = get_salt()
    return hashlib.sha256(salt.encode() + value.encode()).hexdigest()


def create_admin_api_key():
    session = next(get_session())  # is this really the right way to get the session?
    admin_api_key_encrypted = get_fastapi_config().ADMIN_API_KEY_SHA256
    api_key = session.get(APIKey, admin_api_key_encrypted)  # already exists
    if api_key:
        return api_key

    _ = get_salt()  # if salt is not set, environment is not configured properly
    api_key = APIKey(
        encrypted_key=admin_api_key_encrypted,
        is_admin=True,
        is_active=True,
        created_at=datetime.now(),
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    return api_key


def check_authentication_header(
    x_api_key: str = Depends(X_API_KEY),
    session=Depends(get_session),
) -> APIKeyRead:
    """Takes the X-API-Key header and converts it into the matching user object
    from the database."""

    api_key = session.get(APIKey, encrypt(x_api_key))
    if api_key:
        # TODO: implement datetime expiration checking
        if api_key.is_active:
            return APIKeyRead.from_orm(api_key)  # don't inclue the actual key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )


def check_authentication_header_admin(
    authorized_user=Depends(check_authentication_header),
) -> APIKeyRead:

    if authorized_user.is_admin:
        return authorized_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )
