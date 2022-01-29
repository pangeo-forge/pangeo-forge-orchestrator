from fastapi import FastAPI

from .database import maybe_create_db_and_tables
from .routers.model_router import router as model_router
from .routers.security import api_key_router
from .security import create_admin_api_key

app = FastAPI()


@app.on_event("startup")
def on_startup():
    maybe_create_db_and_tables()
    create_admin_api_key()


app.include_router(model_router)
app.include_router(api_key_router)
