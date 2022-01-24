import os
import hashlib
import uuid

from fastapi import FastAPI, Depends

from .database import get_session
from .model_builders import register_endpoints
from .models import MODELS
from .models import APIKey, APIKeyNew, APIKeyCreate
from .security import check_authentication_header

app = FastAPI()


for k in MODELS.keys():
    register_endpoints(app, models=MODELS[k], get_session=get_session)


@app.post("/api-keys/new", response_model=APIKeyNew)
def new_api_key(*,
    key_params: APIKeyCreate,
    session=Depends(get_session),
    authorized_user=Depends(check_authentication_header_admin)
    ):
    raw_key = uuid.uuid4().hex
    encrypted_key = _encrypt(raw_key)

    api_key = APIKey(
        encrypted_key=encrypted_key,
        created_at=datetime.now,
        is_active=True
        **key_params.dict(),  # should only contain is_admin
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    api_key_response_from_db = api_key.to_dict()
    del api_key_response_from_db['encrypted_key']

    api_key_response = APIKeyNew(
        key=raw_key,
        **api_key_response_from_db.dict()
    )

    return api_key_response
