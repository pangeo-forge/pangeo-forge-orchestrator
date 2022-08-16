import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from traitlets import Integer, List, Unicode
from traitlets.config import Application

from .database import maybe_create_db_and_tables
from .http import http_session
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


class GitHubApp(Application):
    installation_id = Integer(
        None,
        allow_none=True,
        config=True,
        help="""
        The installation id for this app instance.
        """,
    )

    webhook_url = Unicode(
        None,
        allow_none=True,
        config=True,
        help="""
        The url to which this app instance sends webhooks.
        """,
    )

    private_key = Unicode(
        None,
        allow_none=True,
        config=True,
        help="""
        The private key for this app instance.
        """,
    )

    run_only_on = List(
        Unicode,
        default=[],
        config=True,
        help="""
        List of labels a PR could have that will trigger a run from this app.

        Leave blank to trigger on everything.
        """,
    )


github_app = GitHubApp()
github_app.load_config_file("github_app.json")


@app.on_event("startup")
def on_startup():
    maybe_create_db_and_tables()
    create_admin_api_key()
    http_session.start()


@app.on_event("shutdown")
def on_shutdown():
    # TODO: make this function async, and await .stop() below
    # Something about the two testing paradigms (sync + async) breaks when I do this now
    http_session.stop()


app.include_router(model_router)
app.include_router(api_key_router)
app.include_router(stats_router)
app.include_router(github_app_router)


@app.get("/", include_in_schema=False)
def status():
    return {"status": "ok"}
