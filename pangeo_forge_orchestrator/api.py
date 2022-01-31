import os

from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from .database import maybe_create_db_and_tables
from .metadata import app_metadata
from .routers.model_router import router as model_router
from .routers.security import api_key_router
from .security import create_admin_api_key

app = FastAPI(**app_metadata)

if os.environ.get("PANGEO_FORGE_DEPLOYMENT", False):
    app.add_middleware(HTTPSRedirectMiddleware)


@app.on_event("startup")
def on_startup():
    maybe_create_db_and_tables()
    create_admin_api_key()


app.include_router(model_router)
app.include_router(api_key_router)


@app.get("/", include_in_schema=False)
def status():
    return {"status": "ok"}
