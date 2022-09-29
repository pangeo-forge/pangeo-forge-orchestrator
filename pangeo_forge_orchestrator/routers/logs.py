from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, SQLModel, select

from ..dependencies import get_session as get_database_session

logs_router = APIRouter()


@logs_router.get(
    "/recipe_runs/{id}/logs",
    summary=" ",
    tags=["", "", "admin"],
)
async def get_recipe_run_logs(
    id: int,
    db_session: Session = Depends(get_database_session),
):
    ...
