import os

import pytest
import subprocess

subcommands = {
    "ls": (
        "['devseed.bakery.development.aws.us-west-2',"
        "'devseed.bakery.development.azure.westeurope','great_bakery']"
    ),
    "ls --bakery-id great_bakery": (
         "{'targets':{'osn':{'fsspec_open_kwargs':{'anon':True,'client_kwargs':{'endpoint_url':"
         "'https://ncsa.osn.xsede.org'}},'protocol':'s3','bakery_root':'Pangeo/pangeo-forge'}}}"
    ),
    "ls --bakery-id great_bakery --view build-logs --feedstock-id noaa-oisst": (
        "┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━"
        "━━━━━━━━━━━━━━━━━━┓┃RunID┃Timestamp┃Feedstock┃Recipe┃Path┃┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━"
        "╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩│00000│2021-"
        "09-2500:00:00│noaa-oisst-avhrr-only-feedstock@1.0│recipe│noaa_oisst/v2.1-avhrr.zarr│└────"
        "────┴─────────────────────┴─────────────────────────────────────┴────────┴───────────────"
        "─────────────┘"
    ),
}
subcommands = [(cmd, output) for cmd, output in subcommands.items()]


@pytest.mark.parametrize("subcmd", subcommands)
def test_bakery_ls(subcmd):
    cmd = ["pangeo-forge", "bakery"]
    for arg in subcmd[0].split(" "):
        cmd.append(arg)
    env = dict(os.environ, COLUMNS="200")
    out = subprocess.check_output(cmd, env=env)
    out = out.decode("utf-8")
    for char in ("\n", " "):
        out = out.replace(char, "")
    assert out == subcmd[1]
