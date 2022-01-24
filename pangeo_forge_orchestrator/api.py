import hashlib
import os
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI

from .database import create_sqlite_db_and_tables, engine, get_session
from .model_builders import register_endpoints
from .models import MODELS, APIKey, APIKeyCreate, APIKeyNew
from .security import check_authentication_header_admin, create_admin_api_key, encrypt

app = FastAPI()


@app.on_event("startup")
def on_startup():
    print("STARTUP!")
    if engine.url.drivername == "sqlite":
        create_sqlite_db_and_tables()

    for session in get_session():
        create_admin_api_key(session)

for k in MODELS.keys():
    register_endpoints(app, models=MODELS[k], get_session=get_session)


@app.post("/api-keys/new", response_model=APIKeyNew)
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
        ** key_params.dict(),  # should only contain is_admin
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    api_key_response_from_db = api_key.dict()
    del api_key_response_from_db["encrypted_key"]

    api_key_response = APIKeyNew(key=raw_key, **api_key_response_from_db)

    return api_key_response
