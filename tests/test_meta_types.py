import pytest
import fsspec
import yaml
from pydantic import ValidationError

from pangeo_forge_orchestrator.meta_types.bakery import BakeryMeta


@pytest.fixture(scope="session")
def bakery_meta_dict(mock_github_http_server):
    _, _, bakery_meta_http_path = mock_github_http_server
    with fsspec.open(bakery_meta_http_path) as f:
        d = yaml.safe_load(f.read())
        d = d[list(d)[0]]
    return d


@pytest.mark.parametrize("invalidate", [None, "keys", "vals"])
def test_bakery_meta(bakery_meta_dict, invalidate):
    d = bakery_meta_dict
    if not invalidate:
        bm = BakeryMeta(**d)
        assert bm is not None
    elif invalidate == "keys":
        for i in range(len(list(d))):
            key = list(d)[i]
            d_copy = d.copy()
            invalid_key = key[1:]
            d_copy[invalid_key] = d_copy[key]
            del d_copy[key]
            with pytest.raises(TypeError):
                BakeryMeta(**d_copy)
    elif invalidate == "vals":
        for k, v in d.items():
            v = str(v) if type(v) != str else v[1:]
            d_copy = d.copy()
            d_copy[k] = v
            with pytest.raises(ValidationError):
                BakeryMeta(**d_copy)


def test_cluster(bakery_meta_dict):
    d = bakery_meta_dict["cluster"]
    if type(d) is None:
        # This might not be allowable in production, but allowing it for now to make it easier to
        # draft the first round of these tests.
        return
    elif type(d) == dict:
        # Our fixtures don't support his at the moment; but this will be the default in production.
        pass


def test_fargate_cluster_options():
    # Not yet included in our fixture.
    pass


# @pytest.mark.parametrize("invalidate", [None, "keys", "vals"])
def test_target(bakery_meta_dict):
    k = list(bakery_meta_dict["targets"])[0]
    d = bakery_meta_dict["targets"][k]
    assert d is not None
