import datetime as dt

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from starlette import status
from .database import get_session
from .models import APIKey, APIKeyRead


X_API_KEY = APIKeyHeader(name='X-API-Key')


def encrypt(value: str) -> str:
    salt = os.environ["ENCRYPTION_SALT"]
    return hashlib.sha256(
        salt.encode() +
        value.encode()
    ).hexdigest()


def check_authentication_header(
    x_api_key: str = Depends(X_API_KEY),
    session=Depends(get_session),
    ) -> APIKeyRead:
    """ takes the X-API-Key header and converts it into the matching user object from the database """

    api_key = session.get(table_cls, encrypt(x_api_key))
    if api_key:
        # TODO: implement datetime expiration checking
        if api_key.is_active:
            return APIKeyRead.from_orm(api_key)  # don't inclue the actual key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )


def check_authentication_header_admin(
    authorized_user=Depends(check_authentication_header)):
    ) -> APIKeyRead:

    if authorized_user.is_admin:
        return authorized_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )
