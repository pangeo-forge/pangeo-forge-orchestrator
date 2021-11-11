import os

import pytest

from .check_stdout import check_stdout

logs_table = (
    "┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓"
    "┃ RunID  ┃     Timestamp       ┃     Feedstock      ┃ Recipe ┃       Path        ┃"
    "┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩"
    "│{run_id}│    {timestamp}      │   {fstock_name}    │{recipe}│    {zarr_path}    │"
    "└────────┴─────────────────────┴────────────────────┴────────┴───────────────────┘"
)
cmds_and_responses = [
    ["ls", "['{bakery_name}']"],
    ["ls --bakery-name {bakery_name}", "{meta_yaml_dict}"],
    # TODO: more entries for build logs fixture, so the full & filtered tables are not identical
    ["ls --bakery-name {bakery_name} --view build-logs", logs_table],
    ["ls --bakery-name {bakery_name} --view build-logs --feedstock-id {fstock_name}", logs_table],
]


@pytest.fixture(scope="session", params=[False, True])
def database_path_from_env(request):
    return request.param


@pytest.fixture(scope="session", params=[*cmds_and_responses])
def bakery_subcommand(
    request, database_path_from_env, github_http_server, bakery_http_server, drop_chars=("\n", " "),
):
    _, bakery_database_entry, bakery_database_http_path = github_http_server
    bakery_name = list(bakery_database_entry)[0]
    build_logs_dict = bakery_http_server[-1].to_dict(orient="index")
    run_id = list(build_logs_dict)[0]
    if database_path_from_env:
        os.environ["PANGEO_FORGE_BAKERY_DATABASE"] = bakery_database_http_path
    else:
        request.param[0] = request.param[0].replace(
            "ls", f"ls --bakery-database-path {bakery_database_http_path}"
        )
    substitutions = {
        "{bakery_name}": bakery_name,
        "{meta_yaml_dict}": str(bakery_database_entry[bakery_name]),
        "{fstock_name}": build_logs_dict[run_id]["feedstock"],
        "{run_id}": str(run_id),
        "{timestamp}": str(build_logs_dict[run_id]["timestamp"]),
        "{recipe}": build_logs_dict[run_id]["recipe"],
        "{zarr_path}": build_logs_dict[run_id]["path"],
    }
    for i, cmd_or_resp in enumerate(request.param):
        for k in substitutions.keys():
            if k in cmd_or_resp:
                request.param[i] = request.param[i].replace(k, substitutions[k])

    return request.param, drop_chars


def test_bakery_ls(bakery_subcommand):
    cmd_and_resp, drop_chars = bakery_subcommand
    eval_dict = False if "'protocol': 'http'" not in cmd_and_resp[1] else True
    check_stdout(cmd_and_resp, module="bakery", drop_chars=drop_chars, eval_dict=eval_dict)
