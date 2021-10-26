import pytest
from pydantic import ValidationError

from pangeo_forge_orchestrator.components import Bakery, FeedstockMetadata
from pangeo_forge_orchestrator.meta_types.bakery import BakeryMeta


@pytest.mark.parametrize("database_yaml", ["valid", "invalid"])
def test_bakery_component(database_yaml, github_http_server):
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    id = list(bakery_database_entry)[0]
    if database_yaml == "valid":
        b = Bakery(id=id, path=bakery_database_http_path)
        assert b.bakeries == bakery_database_entry
        bakery_name = list(b.bakeries)[0]
        bm = BakeryMeta(**b.bakeries[bakery_name])
        assert bm is not None
    else:
        with pytest.raises(ValidationError):
            path = bakery_database_http_path.replace("://", "")
            Bakery(id=id, path=path)


def test_feedstock_metadata():
    f_id = "noaa-oisst-avhrr-only-feedstock@1.0"
    f = FeedstockMetadata(feedstock_id=f_id)
    assert f is not None
