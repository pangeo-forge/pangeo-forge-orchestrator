import os

from sqlmodel import Session, create_engine, select

from pangeo_forge_orchestrator.models import MODELS


def test_db_backup():
    database_url = os.environ["DATABASE_URL"]
    connect_args = dict(options="-c timezone=utc")
    engine = create_engine(database_url, echo=False, connect_args=connect_args)
    with Session(engine) as session:
        statement = select(MODELS["feedstock"].table)
        fstocks = session.exec(statement).all()
        print(fstocks)
