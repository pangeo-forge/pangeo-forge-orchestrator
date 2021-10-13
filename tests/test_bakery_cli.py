import pytest

from .check_stdout import check_stdout

subcommands = {
    "ls": (
        "['devseed.bakery.development.aws.us-west-2',"
        "'devseed.bakery.development.azure.westeurope','test_bakery']"
    ),
    "ls --bakery-id test_bakery": (
        "{'targets':{'local_server':{'bakery_root':'{url}/test-bakery0','fsspec_open_kwargs':{},"
        "'protocol':'http'}}}"
    ),
    "ls --bakery-id test_bakery --view build-logs --feedstock-id mock-feedstock": (
        "┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓"
        "┃RunID┃Timestamp┃Feedstock┃Recipe┃Path┃"
        "┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩"
        "│00000│2021-09-2500:00:00│mock-feedstock│recipe│test-dataset.zarr│"
        "└────────┴─────────────────────┴────────────────┴────────┴───────────────────┘"
    ),
}
subcommands = [[cmd, output] for cmd, output in subcommands.items()]


@pytest.fixture(scope="session", params=[*subcommands])
def bakery_subcommand(request, bakery_http_server):
    url = bakery_http_server[0].split("://")[1]
    bakery_meta_http_path = bakery_http_server[-1]

    request.param[0] = request.param[0].replace(
        "ls", f"ls --extra-bakery-yaml {bakery_meta_http_path}"
    )
    if "{url}" in request.param[1]:
        request.param[1] = request.param[1].replace("{url}", url)
    return request.param


def test_bakery_ls(bakery_subcommand):
    check_stdout(bakery_subcommand, module="bakery", drop_chars=("\n", " "))
