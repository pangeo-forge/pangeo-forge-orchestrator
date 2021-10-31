import copy

import fsspec
import pytest
import yaml
from pydantic import ValidationError

from pangeo_forge_orchestrator.meta_types.bakery import (
    BakeryDatabase,
    BakeryMeta,
    BakeryName,
    BuildLogs,
    Endpoint,
    RunRecord,
    StorageOptions,
    Target,
)

# Helpers -----------------------------------------------------------------------------------------


def invalidate_keys(d, key):
    d_copy = copy.deepcopy(d)
    invalid_key = key[1:]
    d_copy[invalid_key] = d_copy[key]
    del d_copy[key]
    return d_copy


def invalidate_vals(d, k, v):
    d_copy = copy.deepcopy(d)
    if type(v) == dict:
        # make dictionaries unparsable for Pydantic
        v = str(v).replace("{", "")
        v = v.replace(":", "")
        v = v.replace("}", "")
    v = str(v) if type(v) != str else v[1:]
    v = v if v not in ("True", "False") else "String which Pydantic can't parse to boolean value."
    d_copy[k] = v
    return d_copy


# Fixtures ----------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def bakery_meta_dict(github_http_server):
    _, _, bakery_meta_http_path = github_http_server
    with fsspec.open(bakery_meta_http_path) as f:
        d = yaml.safe_load(f.read())
        d = d[list(d)[0]]
    return d


# Tests -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("invalid", [None, "region", "missing-bakery-substring"])
def test_bakery_name(invalid, github_http_server):
    _, bakery_database_entry, _ = github_http_server
    name = list(bakery_database_entry)[0]
    if not invalid:
        bn = BakeryName(name=name)
        assert bn.organization_url == "https://test.org"
    elif invalid == "region":
        with pytest.raises(ValidationError):
            BakeryName(name=name[:-1])
    elif invalid == "missing-bakery-substring":
        with pytest.raises(ValidationError):
            BakeryName(name=name.replace(".bakery.", ""))


@pytest.mark.parametrize("invalid", [None, "database_path"])
def test_bakery_database(invalid, github_http_server):
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    if not invalid:
        bd = BakeryDatabase(path=bakery_database_http_path)
        assert bd is not None
        assert bd.bakeries == bakery_database_entry
    elif invalid == "database_path":
        with pytest.raises(ValidationError):
            path = bakery_database_http_path.replace("://", "")
            BakeryDatabase(path=path)


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
                with pytest.raises(ValidationError):
                    StorageOptions(**d_copy)


@pytest.mark.parametrize("invalid", [None, "timestamp", "feedstock", "recipe", "path"])
def test_run_record(invalid, bakery_http_server, invalid_feedstock_names):
    logs = bakery_http_server[-1]

    for k in logs.keys():
        if not invalid:
            RunRecord(**logs[k])
        elif invalid == "timestamp":
            logs_copy = copy.deepcopy(logs)
            logs_copy[k]["timestamp"] = "String which is not parsable to datetime."
            with pytest.raises(ValidationError):
                RunRecord(**logs_copy[k])
        elif invalid == "feedstock":
            logs_copy = copy.deepcopy(logs)
            for fstock_name in invalid_feedstock_names:
                logs_copy[k]["feedstock"] = fstock_name
                with pytest.raises(ValidationError):
                    RunRecord(**logs_copy[k])
        elif invalid == "recipe":
            logs_copy = copy.deepcopy(logs)
            for invalid_recipe_name in (
                # recipe object must be a valid python identifier
                "recipe&",
                "1recipe",
                "rec-ipe",
                # if colon delimiter is used, a dictionary key must follow it
                "recipe:",
                # dictionary key special characters can only be dash or underscore (relax this?)
                "recipe:key&with*special$characters",
            ):
                logs_copy[k]["recipe"] = invalid_recipe_name
                with pytest.raises(ValidationError):
                    RunRecord(**logs_copy[k])
        elif invalid == "path":
            # only requirement is that path is a string; pydantic will parse anything into a str
            pass


@pytest.mark.parametrize("invalid", [None, "run_id", "runrecord"])
def test_build_logs(invalid, bakery_http_server):
    logs = bakery_http_server[-1]

    if not invalid:
        BuildLogs(logs=logs)
    elif invalid == "run_id":
        logs_copy = copy.deepcopy(logs)
        # run_ids can only contain integer characters from 0-9
        for invalid_character in (
            "A",
            "a",
            "_",
        ):
            logs_copy = {f"{k}{invalid_character}": v for k, v in logs_copy.items()}
            with pytest.raises(ValidationError):
                BuildLogs(logs=logs_copy)
    elif invalid == "runrecord":
        logs_copy = copy.deepcopy(logs)
        # ensure that `RunRecord` objects are validated from within `BuildLogs`
        for k in logs.keys():
            logs_copy[k]["timestamp"] = "String which is not parsable to datetime."
            with pytest.raises(ValidationError):
                BuildLogs(logs=logs_copy)
