import json

import pytest
import xarray as xr

from .cli_test_funcs import check_output

item = {
    'type': 'Feature',
    'stac_version': '1.0.0',
    'id': 'noaa-oisst-avhrr-only-feedstock@1.0',
    'properties': {
        'cube:dimensions': {
            'time': {
                'type': 'temporal',
                'description': 'Center time of the day',
                'extent': ['1981-09-01T12:00:00Z', '2021-06-14T12:00:00Z'],
                'step': 'P1DT0H0M0S'
            },
            'lon': {
                'type': 'spatial',
                'axis': 'x',
                'description': 'Longitude',
                'extent': [0.125, 359.875],
                'step': 0.25
            },
            'lat': {
                'type': 'spatial',
                'axis': 'y',
                'description': 'Latitude',
                'extent': [-89.875, 89.875],
                'step': 0.25
            }
        },
        'cube:variables': {
            'anom': {
                'type': 'data',
                'description': 'Daily sea surface temperature anomalies',
                'dimensions': ['time', 'zlev', 'lat', 'lon'],
                'unit': 'Celsius',
                'shape': [14532, 1, 720, 1440],
                'chunks': [20, 1, 720, 1440],
                'attrs': {
                    'long_name': 'Daily sea surface temperature anomalies',
                    'units': 'Celsius',
                    'valid_max': 1200,
                    'valid_min': -1200
                }
            },
            'err': {
                'type': 'data',
                'description': 'Estimated error standard deviation of analysed_sst',
                'dimensions': ['time', 'zlev', 'lat', 'lon'],
                'unit': 'Celsius',
                'shape': [14532, 1, 720, 1440],
                'chunks': [20, 1, 720, 1440],
                'attrs': {
                    'long_name': 'Estimated error standard deviation of analysed_sst',
                    'units': 'Celsius',
                    'valid_max': 1000,
                    'valid_min': 0
                }
            },
            'ice': {
                'type': 'data',
                'description': 'Sea ice concentration',
                'dimensions': ['time', 'zlev', 'lat', 'lon'],
                'unit': '%',
                'shape': [14532, 1, 720, 1440],
                'chunks': [20, 1, 720, 1440],
                'attrs': {
                    'long_name': 'Sea ice concentration',
                    'units': '%',
                    'valid_max': 100,
                    'valid_min': 0
                }
            },
            'sst': {
                'type': 'data',
                'description': 'Daily sea surface temperature',
                'dimensions': ['time', 'zlev', 'lat', 'lon'],
                'unit': 'Celsius',
                'shape': [14532, 1, 720, 1440],
                'chunks': [20, 1, 720, 1440],
                'attrs': {
                    'long_name': 'Daily sea surface temperature',
                    'units': 'Celsius',
                    'valid_max': 4500,
                    'valid_min': -300
                }
            }
        },
        'datetime': None,
        'start_datetime': '1981-09-01T12:00:00Z',
        'end_datetime': '2021-06-14T12:00:00Z'
    },
    'geometry': {
        'type': 'Polygon',
        'coordinates': [
            [
                [89.875, 0.125],
                [89.875, 359.875],
                [-89.875, 359.875],
                [-89.875, 0.125],
                [89.875, 0.125]]
        ]
    },
    'links': [],
    'assets': {
        'zarr-https': {
            'href': 'https://ncsa.osn.xsede.org/Pangeo/pangeo-forge/noaa_oisst/v2.1-avhrr.zarr',
            'type': 'application/vnd+zarr',
            'title': 'NOAA Optimum Interpolated SST - HTTPS Zarr root',
            'description': (
                'HTTPS Zarr root for analysis-ready Zarr datasets derived from NOAA OISST NetCDF'
            ),
            'xarray:open_kwargs': {'consolidated': True},
            'roles': ['data', 'zarr', 'https']
        },
        'zarr-s3': {
            'href': 's3://Pangeo/pangeo-forge/noaa_oisst/v2.1-avhrr.zarr',
            'type': 'application/vnd+zarr',
            'title': 'NOAA Optimum Interpolated SST - S3 File System Zarr root',
            'description': (
                'S3 File System Zarr root for analysis-ready'
                ' Zarr datasets derived from NOAA OISST NetCDF'
            ),
            'xarray:storage_options': {
                'anon': True, 'client_kwargs': {'endpoint_url': 'https://ncsa.osn.xsede.org'}
            },
            'xarray:open_kwargs': {'consolidated': True},
            'roles': ['data', 'zarr', 's3']
        },
        'pangeo-forge-feedstock': {
            'href': 'https://github.com/pangeo-forge/noaa-oisst-avhrr-only-feedstock/tree/v1.0',
            'type': '',
            'title': (
                'Pangeo Forge Feedstock (GitHub repository) for noaa-oisst-avhrr-only-feedstock@1.0'
            )
        },
        'jupyter-notebook-example-https': {'href': '_', 'type': '', 'title': ''},
        'jupyter-notebook-example-s3': {'href': '_', 'type': '', 'title': ''}
    },
    'bbox': [-89.875, 0.125, 89.875, 359.875],
    'stac_extensions': ['https://stac-extensions.github.io/datacube/v2.0.0/schema.json']
}

item = json.dumps(item)

replacements = [("\"", "'"), (" ", ""), ("true", "True"), ("null", "None")]
for r in replacements:
    item = item.replace(r[0], r[1])

subcommands = {"make-stac-item great_bakery 00000": item}
subcommands = [(cmd, output) for cmd, output in subcommands.items()]


#@pytest.mark.parametrize("subcmd", subcommands)
#def test_catalog_make_stac_item(subcmd):
#    check_output(subcmd, module="catalog", drop_chars=("\n", " "))


def test_server(bakery_http_path):
    url, zarr_path = bakery_http_path
    ds = xr.open_zarr(zarr_path, consolidated=True)
    print(ds)
