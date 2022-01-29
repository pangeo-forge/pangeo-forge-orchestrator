import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from ..dependencies import check_authentication_header_admin, get_session
from ..models import APIKey, APIKeyCreate, APIKeyNew
from ..security import encrypt

api_key_router = APIRouter()


@api_key_router.post("/api-keys", response_model=APIKeyNew)
def new_api_key(
    *,
    key_params: APIKeyCreate,
    session=Depends(get_session),
    authorized_user=Depends(check_authentication_header_admin)
):
    raw_key = uuid.uuid4().hex
    encrypted_key = encrypt(raw_key)

    api_key = APIKey(
        encrypted_key=encrypted_key,
        created_at=datetime.now,
        is_active=True,
        **key_params.dict(),  # should only contain is_admin
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    api_key_response_from_db = api_key.dict()
    del api_key_response_from_db["encrypted_key"]

    api_key_response = APIKeyNew(key=raw_key, **api_key_response_from_db)

    return api_key_response


# TODO: implement listing, updating, deleting keys
