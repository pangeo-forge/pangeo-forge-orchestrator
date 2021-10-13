import pytest

from .cli_test_funcs import check_output

subcommands = {
    "ls": (
        "['devseed.bakery.development.aws.us-west-2',"
        "'devseed.bakery.development.azure.westeurope']"
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
subcommands = [(cmd, output) for cmd, output in subcommands.items()]


@pytest.mark.parametrize("subcmd", subcommands)
def test_bakery_ls(subcmd):
    check_output(subcmd, module="bakery", drop_chars=("\n", " "))
