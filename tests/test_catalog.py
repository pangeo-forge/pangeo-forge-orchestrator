import json
import os

import pytest

from pangeo_forge_orchestrator.catalog import generate


@pytest.mark.parametrize("to_file", [False, True])
@pytest.mark.parametrize("execute_notebooks", [False, True])
def test_generate(
    github_http_server, bakery_http_server, stac_item_result, to_file, execute_notebooks,
):
    _ = bakery_http_server  # start bakery server
    github_http_base, bakery_database_entry, bakery_database_http_path = github_http_server
    bakery_name = list(bakery_database_entry)[0]
    kw = dict(
        bakery_name=bakery_name,
        run_id="00000",
        bakery_database_path=bakery_database_http_path,
        bakery_stac_relative_path="",
        feedstock_metadata_url_base=github_http_base,
        to_file=to_file,
        execute_notebooks=execute_notebooks,
        endpoints=["http"],
    )
    if to_file is False and execute_notebooks is True:
        with pytest.raises(ValueError):
            generate(**kw)
    else:
        gen_result = generate(**kw)
        assert gen_result == stac_item_result

        if to_file:
            with open(f"{gen_result['id']}.json") as f:
                on_disk = json.loads(f.read())
            assert gen_result == on_disk == stac_item_result

            os.remove(f"{gen_result['id']}.json")
            if execute_notebooks:
                os.remove(f"{gen_result['id']}_via_http.ipynb")

            # TODO: validate notebook output; possibly by checking for:
            # "<style>/* CSS stylesheet for displaying xarray objects in jupyterlab.\n" ?
