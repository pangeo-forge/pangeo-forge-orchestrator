import pytest
import fsspec
import yaml
from pydantic import ValidationError

from pangeo_forge_orchestrator.meta_types.bakery import BakeryMeta, Endpoint, StorageOptions, Target


def invalidate_keys(d, key):
    d_copy = d.copy()
    invalid_key = key[1:]
    d_copy[invalid_key] = d_copy[key]
    del d_copy[key]
    return d_copy


def invalidate_vals(d, k, v):
    d_copy = d.copy()
    if type(v) == dict:
        # make dictionaries unparsable for Pydantic
        v = str(v).replace("{", "")
        v = v.replace(":", "")
        v = v.replace("}", "")
    v = str(v) if type(v) != str else v[1:]
    v = v if v not in ("True", "False") else "String which Pydantic can't parse to boolean value."
    d_copy[k] = v
    return d_copy


@pytest.fixture(scope="session")
def bakery_meta_dict(github_http_server):
    _, _, bakery_meta_http_path = github_http_server
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
            d_copy = invalidate_keys(d, key=list(d)[i])
            with pytest.raises(TypeError):
                BakeryMeta(**d_copy)
    elif invalidate == "vals":
        for k, v in d.items():
            d_copy = invalidate_vals(d, k, v)
            with pytest.raises(ValidationError):
                BakeryMeta(**d_copy)


def test_cluster(bakery_meta_dict):
    d = bakery_meta_dict["cluster"]
    if type(d) is None:
        # Maybe not be allowable in prod, but allowing it for now to make first draft simpler.
        return
    elif type(d) == dict:
        # Our fixtures don't support his at the moment; but this will be the default in prod.
        pass


def test_fargate_cluster_options():
    # Not yet included in our fixture.
    pass


@pytest.mark.parametrize("invalidate", [None, "region"])
def test_target(bakery_meta_dict, invalidate):
    # TODO: add key invalidation raises TypeError, as in `test_bakery_meta`.
    k = list(bakery_meta_dict["targets"])[0]
    d = bakery_meta_dict["targets"][k]
    if not invalidate:
        Target(**d)
    elif invalidate == "region":
        d["region"] = d["region"][1:]
        with pytest.raises(ValidationError):
            Target(**d)


@pytest.mark.parametrize("endpoint", ["public", "private"])
@pytest.mark.parametrize("invalidate", [None, "protocol"])
def test_endpoint(bakery_meta_dict, endpoint, invalidate):
    # Redundant w/ `test_target` & `test_storage_options` but not 1:1 given loop and `d` assignment.
    # TODO: add key invalidation raises TypeError, as in `test_bakery_meta`.
    k = list(bakery_meta_dict["targets"])[0]
    d = bakery_meta_dict["targets"][k][endpoint]
    if not invalidate:
        Endpoint(**d)
    elif invalidate == "protocol":
        d["protocol"] = d["protocol"][1:]
        with pytest.raises(ValidationError):
            Endpoint(**d)


@pytest.mark.parametrize("endpoint", ["public", "private"])
@pytest.mark.parametrize("invalidate", [None, "keys", "vals"])
def test_storage_options(bakery_meta_dict, endpoint, invalidate):
    k = list(bakery_meta_dict["targets"])[0]
    d = bakery_meta_dict["targets"][k][endpoint]["storage_options"]
    if not invalidate:
        StorageOptions(**d)
    else:
        if invalidate == "keys":
            for i in range(len(list(d))):
                d_copy = invalidate_keys(d, key=list(d)[i])
                with pytest.raises(ValidationError):
                    StorageOptions(**d_copy)

        elif invalidate == "vals":
            for k, v in d.items():
                d_copy = invalidate_vals(d, k, v)
                print("D is THIS:", d)
                print("D_COPY is THIS:", d_copy)
                with pytest.raises(ValidationError):
                    StorageOptions(**d_copy)
