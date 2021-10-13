import pytest

from .check_stdout import check_stdout

subcommands = {
    "ls": (
        "['devseed.bakery.development.aws.us-west-2',"
        "'devseed.bakery.development.azure.westeurope','test_bakery']"
    ),
    #"ls --bakery-id great_bakery": (
    #     "{'targets':{'osn':{'fsspec_open_kwargs':{'anon':True,'client_kwargs':{'endpoint_url':"
    #     "'https://ncsa.osn.xsede.org'}},'protocol':'s3','bakery_root':'Pangeo/pangeo-forge'}}}"
    #),
    #"ls --bakery-id great_bakery --view build-logs --feedstock-id noaa-oisst": (
    #    "┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━"
    #    "━━━━━━━━━━━━━━━━━━┓┃RunID┃Timestamp┃Feedstock┃Recipe┃Path┃┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━"
    #    "╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩│00000│2021-"
    #    "09-2500:00:00│noaa-oisst-avhrr-only-feedstock@1.0│recipe│noaa_oisst/v2.1-avhrr.zarr│└────"
    #    "────┴─────────────────────┴─────────────────────────────────────┴────────┴───────────────"
    #    "─────────────┘"
    #),
}
subcommands = [[cmd, output] for cmd, output in subcommands.items()]


@pytest.fixture(scope="session", params=[*subcommands])
def bakery_subcommand(request, bakery_http_server):
    bakery_meta_http_path = bakery_http_server[-1]
    request.param[0] = request.param[0].replace(
        "ls", f"ls --extra-bakery-yaml {bakery_meta_http_path}"
    )
    return request.param


def test_bakery_ls(bakery_subcommand):
    check_stdout(bakery_subcommand, module="bakery", drop_chars=("\n", " "))
