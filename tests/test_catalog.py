import json
import os
from pathlib import Path

import pytest

from pangeo_forge_orchestrator.catalog import generate


@pytest.fixture(scope="session")
def stac_item_result(bakery_http_server):
    bakery_http_base = bakery_http_server[1]
    local_bakery_port = bakery_http_base.split("127.0.0.1:")[1][:5]
    result = {
        'type': 'Feature',
        'stac_version': '1.0.0',
        'id': 'mock-feedstock@1.0',
        'properties': {
            'cube:dimensions': {
                'time': {
                    'type': 'temporal',
                    'extent': ['2010-01-01T00:00:00Z', '2010-01-10T00:00:00Z'],
                    'step': 'P1DT0H0M0S',
                },
                'lon': {
                    'type': 'spatial',
                    'axis': 'x',
                    'description': 'longitude',
                    'extent': [5.0, 355.0],
                    'step': 10.0,
                },
                'lat': {
                    'type': 'spatial',
                    'axis': 'y',
                    'description': 'latitude',
                    'extent': [5.0, 175.0],
                    'step': 10.0,
                },
            },
            'cube:variables': {
                'bar': {
                    'type': 'data',
                    'description': 'Beautiful Bar',
                    'dimensions': ['time', 'lat', 'lon'],
                    'shape': [10, 18, 36],
                    'chunks': [10, 18, 36],
                    'attrs': {'long_name': 'Beautiful Bar'},
                },
                'foo': {
                    'type': 'data',
                    'description': 'Fantastic Foo',
                    'dimensions': ['time', 'lat', 'lon'],
                    'shape': [10, 18, 36],
                    'chunks': [10, 18, 36],
                    'attrs': {'long_name': 'Fantastic Foo'},
                },
            },
            'datetime': None,
            'start_datetime': '2010-01-01T00:00:00Z',
            'end_datetime': '2010-01-10T00:00:00Z',
        },
        'geometry': {
            'type': 'Polygon',
            'coordinates': [[[175.0, 5.0], [175.0, 355.0], [5.0, 355.0], [5.0, 5.0], [175.0, 5.0]]],
        },
        'links': [],
        'assets': {
            'zarr-http': {
                'href': f'http://127.0.0.1:{local_bakery_port}/test-bakery0/test-dataset.zarr',
                'type': 'application/vnd+zarr',
                'title': 'Mock Feedstock - HTTP File System Zarr root',
                'description': 'HTTP File System Zarr root for random test data.',
                'xarray:open_kwargs': {'consolidated': True},
                'xarray:storage_options': None,
                'roles': ['data', 'zarr', 'http'],
            },
            'pangeo-forge-feedstock': {
                'href': 'https://github.com/pangeo-forge/mock-feedstock/tree/v1.0',  # TODO: fix?
                'type': '',
                'title': 'Pangeo Forge Feedstock (GitHub repository) for mock-feedstock@1.0'
            },
            'jupyter-notebook-example-https': {'href': '_', 'type': '', 'title': ''},
            'jupyter-notebook-example-s3': {'href': '_', 'type': '', 'title': ''},
        },
        'bbox': [5.0, 5.0, 175.0, 355.0],
        'stac_extensions': ['https://stac-extensions.github.io/datacube/v2.0.0/schema.json'],
    }
    return result


@pytest.mark.parametrize("to_file", [False, True])
@pytest.mark.parametrize("execute_notebooks", [False, True])
def test_generate(
    github_http_server,
    bakery_http_server,
    stac_item_result,
    to_file,
    execute_notebooks,
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
            parent = Path(__file__).absolute().parent
            with open(f"{parent}/{gen_result['id']}.json") as f:
                on_disk = json.loads(f.read())
            assert gen_result == on_disk == stac_item_result

            os.remove(f"{gen_result['id']}.json")
            if execute_notebooks:
                os.remove(f"{gen_result['id']}_via_http.ipynb")

            # TODO: validate notebook output; possibly by checking for:
            # "<style>/* CSS stylesheet for displaying xarray objects in jupyterlab.\n" ?
