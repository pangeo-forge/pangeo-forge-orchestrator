"""Seed test data for review apps, so the developer does not need to do this manually
for each review app. This is only called once, following build of a review app. It is not
called on any other apps (staging, prod, etc.). See also:

    app.json -> environments -> review -> scripts -> postdeploy

which is where this script is configured to be called by Heroku.
"""
from sqlmodel import Session

from pangeo_forge_orchestrator.database import engine
from pangeo_forge_orchestrator.models import MODELS

test_staged_recipes = MODELS["feedstock"].table.from_orm(
    MODELS["feedstock"].creation(spec="pforgetest/test-staged-recipes")
)
gpcp_from_gcs = MODELS["feedstock"].table.from_orm(
    MODELS["feedstock"].creation(spec="pforgetest/gpcp-from-gcs-feedstock")
)
default_bakery = MODELS["bakery"].table.from_orm(
    MODELS["bakery"].creation(
        region="foo",
        name="pangeo-ldeo-nsf-earthcube",
        description="bar",
    )
)

to_commit = [test_staged_recipes, gpcp_from_gcs, default_bakery]
with Session(engine) as db_session:
    for model in to_commit:
        db_session.add(model)
        db_session.commit()
