# import pytest

from pangeo_forge_orchestrator.components import BakeryDatabase, FeedstockMetadata


def test_bakery_metadata():
    b = BakeryDatabase()
    assert b is not None


def test_feedstock_metadata():
    f_id = "noaa-oisst-avhrr-only-feedstock@1.0"
    f = FeedstockMetadata(feedstock_id=f_id)
    assert f is not None
