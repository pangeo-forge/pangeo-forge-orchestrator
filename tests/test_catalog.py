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
            'zarr-https': {
                'href': f'https://127.0.0.1:{local_bakery_port}/test-bakery0/test-dataset.zarr',
                'type': 'application/vnd+zarr',
                'title': 'Mock Feedstock - HTTPS Zarr root',
                'description': 'HTTPS Zarr root for random test data.',
                'xarray:open_kwargs': {'consolidated': True},
                'roles': ['data', 'zarr', 'https'],
            },
            'zarr-s3': {
                'href': f's3://127.0.0.1:{local_bakery_port}/test-bakery0/test-dataset.zarr',
                'type': 'application/vnd+zarr',
                'title': 'Mock Feedstock - S3 File System Zarr root',
                'description': 'S3 File System Zarr root for random test data.',
                'xarray:storage_options': {},
                'xarray:open_kwargs': {'consolidated': True},
                'roles': ['data', 'zarr', 's3'],
            },
            'pangeo-forge-feedstock': {
                'href': 'https://github.com/pangeo-forge/mock-feedstock/tree/v1.0',
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


def test_generate(github_http_server, bakery_http_server, stac_item_result):
    _ = bakery_http_server  # start bakery server
    github_http_base, bakery_database_entry, bakery_database_http_path = github_http_server
    bakery_name = list(bakery_database_entry)[0]

    result = generate(
        bakery_name=bakery_name,
        run_id="00000",
        bakery_database_path=bakery_database_http_path,
        feedstock_metadata_url_base=github_http_base,
    )
    assert result == stac_item_result
