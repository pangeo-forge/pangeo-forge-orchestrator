import pytest
from pydantic import ValidationError

from pangeo_forge_orchestrator.components import Bakery, FeedstockMetadata
from pangeo_forge_orchestrator.meta_types.bakery import BakeryMeta


@pytest.mark.parametrize("invalid", [None, "database_path", "bakery_name"])
def test_bakery_component(invalid, github_http_server, bakery_http_server):
    _ = bakery_http_server  # start bakery server
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    name = list(bakery_database_entry)[0]
    if not invalid:
        b = Bakery(name=name, path=bakery_database_http_path)
        assert b.bakeries == bakery_database_entry
        bakery_name = list(b.bakeries)[0]
        bm = BakeryMeta(**b.bakeries[bakery_name])
        print(b.build_logs)
        assert bm is not None
    elif invalid == "database_path":
        with pytest.raises(ValidationError):
            path = bakery_database_http_path.replace("://", "")
            Bakery(name=name, path=path)
    elif invalid == "bakery_name":
        with pytest.raises(ValidationError):
            name = name.replace(".bakery.", "")
            Bakery(name=name, path=bakery_database_http_path)


def test_feedstock_metadata():
    f_id = "noaa-oisst-avhrr-only-feedstock@1.0"
    f = FeedstockMetadata(feedstock_id=f_id)
    assert f is not None
