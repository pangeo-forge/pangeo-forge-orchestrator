import pytest

from .check_stdout import check_stdout

cmds_and_responses = [
    [
        (
            "make-stac-item {bakery_name} {run_id} "
            "--bakery-database-path {bakery_database_path} "
            "--feedstock-metadata-url-base {feedstock_metadata_url_base}"
        ),
        "{item_result}",
    ]
]


@pytest.fixture(scope="session", params=[*cmds_and_responses])
def catalog_subcommand(request, github_http_server, bakery_http_server, stac_item_result):
    # much (but not all) of this is repetitive of the `test_bakery_cli::bakery_subcommand` fixture
    github_http_base, bakery_database_entry, bakery_meta_http_path = github_http_server
    bakery_name = list(bakery_database_entry)[0]
    build_logs_dict = bakery_http_server[-1].to_dict(orient="index")

    substitutions = {
        "{bakery_name}": bakery_name,
        "{run_id}": str(list(build_logs_dict)[0]),
        "{item_result}": str(stac_item_result),
        # TODO: harmonize db naming with bakery cli & `test_bakery_cli::bakery_subcommand` fixture
        "{bakery_database_path}": bakery_meta_http_path,
        "{feedstock_metadata_url_base}": github_http_base,
    }
    for i, cmd_or_resp in enumerate(request.param):
        for k in substitutions.keys():
            if k in cmd_or_resp:
                request.param[i] = request.param[i].replace(k, substitutions[k])

    return request.param


def test_catalog_make_stac_item(catalog_subcommand):
    cmd_and_resp = catalog_subcommand
    check_stdout(cmd_and_resp, module="catalog", drop_chars=("\n", " "), eval_dict=True)
