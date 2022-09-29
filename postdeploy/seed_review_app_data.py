"""Seed test data for review apps, so the developer does not need to do this manually
for each review app. This is only called once, following build of a review app. It is not
called on any other apps (staging, prod, etc.). See also:

    app.json -> environments -> review -> scripts -> postdeploy

which is where this script is configured to be called by Heroku.
"""

from ..pangeo_forge_orchestrator.dependencies import get_session
from ..pangeo_forge_orchestrator.models import MODELS

test_staged_recipes = MODELS["feedstock"].table.from_orm(
    MODELS["feedstock"].creation(spec="pforgetest/test-staged-recipes")
)

to_commit = [test_staged_recipes]
db_session = get_session()
for model in to_commit:
    db_session.add(model)
    db_session.commit()
