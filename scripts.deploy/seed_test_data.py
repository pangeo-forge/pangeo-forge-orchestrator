from pangeo_forge_orchestrator.dependencies import get_session
from pangeo_forge_orchestrator.models import MODELS

test_staged_recipes = MODELS["feedstock"].table.from_orm(
    MODELS["feedstock"].creation(spec="pforgetest/test-staged-recipes")
)

to_commit = [test_staged_recipes]
db_session = get_session()
for model in to_commit:
    db_session.add(model)
    db_session.commit()
