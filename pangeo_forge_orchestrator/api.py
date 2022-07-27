import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from .database import maybe_create_db_and_tables
from .metadata import app_metadata
from .routers.github_app import github_app_router
from .routers.model_router import router as model_router
from .routers.security import api_key_router
from .routers.stats import stats_router
from .security import create_admin_api_key

app = FastAPI(**app_metadata)

if os.environ.get("PANGEO_FORGE_DEPLOYMENT", False):
    app.add_middleware(HTTPSRedirectMiddleware)

origins = ["*"]  # is this dangerous? I can't see why.

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    maybe_create_db_and_tables()
    create_admin_api_key()


app.include_router(model_router)
app.include_router(api_key_router)
app.include_router(stats_router)
app.include_router(github_app_router)


@app.get("/", include_in_schema=False)
def status():
    return {"status": "ok"}
