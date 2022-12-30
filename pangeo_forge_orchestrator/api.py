import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from .configurables import check_secrets_decrypted, get_config_file
from .database import maybe_create_db_and_tables
from .http import http_session
from .metadata import app_metadata
from .routers.github_app import github_app_router
from .routers.model_router import router as model_router
from .routers.repr import repr_router
from .routers.stats import stats_router

app = FastAPI(**app_metadata)

if os.environ.get("PANGEO_FORGE_DEPLOYMENT") in ("prod", "staging"):
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
    assert get_config_file()  # don't need config_file here, but it must exist
    check_secrets_decrypted()  # if we've forgetten to decrypt secrets, bail early
    maybe_create_db_and_tables()
    http_session.start()


@app.on_event("shutdown")
def on_shutdown():
    # TODO: make this function async, and await .stop() below
    # Something about the two testing paradigms (sync + async) breaks when I do this now
    http_session.stop()


app.include_router(model_router)
app.include_router(stats_router)
app.include_router(github_app_router)
app.include_router(repr_router)


@app.get("/", include_in_schema=False)
def status():
    return {"status": "ok"}
