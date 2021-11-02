# Use guide

Via the `pangeo-forge` command line entrypoint, the package defines four sub-modules: `recipe`, `feedstock`, `bakery`, and `catalog`. The former two are currently placeholders with only a boilerplate `--help` command (or, in the case of `recipe` a placeholder `lint` subcommand). Regarding the latter two:

- `bakery` has an `ls` introspection command, which works given the correct arguments (details below)
- `catalog` has a `make-stac-item` command which:
   - generates a STAC Item for a Pangeo Forge dataset
   - (optionally) writes that Item to local disk or to a specified path in the Bakery storage target where the dataset resides
   - (optionally) automatically executes example notebooks demonstrating how to open the specified dataset from the STAC Item

## What _doesn't_ work 🤔

All of what's built so far relies on `pangeo_forge_orchestrator.components.Bakery` as an interface to a given Pangeo Forge Bakery. These instances require a path to a valid Bakery database, and in almost all cases, a valid Bakery name (which also appears in the specified Bakery database). As noted in [pangeo-forge/bakery-database/issues/5](https://github.com/pangeo-forge/bakery-database/issues/5#issue-983377276), our current official Bakery database actually doesn't conform to the spec defined in the Bakery database ADR. Therefore, invoking

```zsh
➜ pangeo-forge bakery ls
```

which should ideally return a list of Bakery names from the official Bakery database, (expectedly) raises Pydantic validation errors:

<details>

<summary> Traceback </summary>

```
Traceback (most recent call last):
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/bin/pangeo-forge", line 5, in <module>
    app()
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/typer/main.py", line 214, in __call__
    return get_command(self)(*args, **kwargs)
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/click/core.py", line 1128, in __call__
    return self.main(*args, **kwargs)
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/click/core.py", line 1053, in main
    rv = self.invoke(ctx)
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/click/core.py", line 1659, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/click/core.py", line 1659, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/click/core.py", line 1395, in invoke
    return ctx.invoke(self.callback, **ctx.params)
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/click/core.py", line 754, in invoke
    return __callback(*args, **kwargs)
  File "/Users/charlesstern1/.pyenv/versions/anaconda3-2019.10/envs/pfo-poetry/lib/python3.8/site-packages/typer/main.py", line 500, in wrapper
    return callback(**use_params)  # type: ignore
  File "/Users/charlesstern1/Dropbox/pangeo/pangeo-forge-orchestrator/pangeo_forge_orchestrator/cli/bakery.py", line 26, in ls
    bakery_db = BakeryDatabase(**kw)
  File "/Users/charlesstern1/Dropbox/pangeo/pangeo-forge-orchestrator/pangeo_forge_orchestrator/meta_types/bakery.py", line 222, in __init__
    self.names = [BakeryName(name=name) for name in list(self.bakeries)]
  File "/Users/charlesstern1/Dropbox/pangeo/pangeo-forge-orchestrator/pangeo_forge_orchestrator/meta_types/bakery.py", line 222, in <listcomp>
    self.names = [BakeryName(name=name) for name in list(self.bakeries)]
  File "<string>", line 6, in __init__
  File "pydantic/dataclasses.py", line 99, in pydantic.dataclasses._generate_pydantic_post_init._pydantic_post_init
    # +=======+=======+=======+
pydantic.error_wrappers.ValidationError: 2 validation errors for BakeryName
region
  unexpected value; permitted: 'aws.us-east-1', 'aws.us-east-2', 'aws.us-west-1', 'aws.us-west-2', 'aws.ca-central-1', 'aws.eu-west-1', 'aws.eu-central-1', 'aws.eu-west-2', 'aws.eu-west-3', 'aws.eu-north-1', 'aws.ap-northeast-1', 'aws.ap-northeast-2', 'aws.ap-southeast-1', 'aws.ap-southeast-2', 'aws.ap-south-1', 'aws.sa-east-1', 'aws.us-gov-west-1', 'aws.us-gov-east-1', 'azure.eastus', 'azure.eastus2', 'azure.southcentralus', 'azure.westus2', 'azure.westus3', 'azure.australiaeast', 'azure.southeastasia', 'azure.northeurope', 'azure.swedencentral', 'azure.uksouth', 'azure.westeurope', 'azure.centralus', 'azure.northcentralus', 'azure.westus', 'azure.southafricanorth', 'azure.centralindia', 'azure.eastasia', 'azure.japaneast', 'azure.jioindiawest', 'azure.koreacentral', 'azure.canadacentral', 'azure.francecentral', 'azure.germanywestcentral', 'azure.norwayeast', 'azure.switzerlandnorth', 'azure.uaenorth', 'azure.brazilsouth', 'azure.centralusstage', 'azure.eastusstage', 'azure.eastus2stage', 'azure.northcentralusstage', 'azure.southcentralusstage', 'azure.westusstage', 'azure.westus2stage', 'azure.asia', 'azure.asiapacific', 'azure.australia', 'azure.brazil', 'azure.canada', 'azure.europe', 'azure.global', 'azure.india', 'azure.japan', 'azure.uk', 'azure.unitedstates', 'azure.eastasiastage', 'azure.southeastasiastage', 'azure.centraluseuap', 'azure.eastus2euap', 'azure.westcentralus', 'azure.southafricawest', 'azure.australiacentral', 'azure.australiacentral2', 'azure.australiasoutheast', 'azure.japanwest', 'azure.jioindiacentral', 'azure.koreasouth', 'azure.southindia', 'azure.westindia', 'azure.canadaeast', 'azure.francesouth', 'azure.germanynorth', 'azure.norwaywest', 'azure.swedensouth', 'azure.switzerlandwest', 'azure.ukwest', 'azure.uaecentral', 'azure.brazilsoutheast' (type=value_error.const; given=development.aws.us-west-2; permitted=('aws.us-east-1', 'aws.us-east-2', 'aws.us-west-1', 'aws.us-west-2', 'aws.ca-central-1', 'aws.eu-west-1', 'aws.eu-central-1', 'aws.eu-west-2', 'aws.eu-west-3', 'aws.eu-north-1', 'aws.ap-northeast-1', 'aws.ap-northeast-2', 'aws.ap-southeast-1', 'aws.ap-southeast-2', 'aws.ap-south-1', 'aws.sa-east-1', 'aws.us-gov-west-1', 'aws.us-gov-east-1', 'azure.eastus', 'azure.eastus2', 'azure.southcentralus', 'azure.westus2', 'azure.westus3', 'azure.australiaeast', 'azure.southeastasia', 'azure.northeurope', 'azure.swedencentral', 'azure.uksouth', 'azure.westeurope', 'azure.centralus', 'azure.northcentralus', 'azure.westus', 'azure.southafricanorth', 'azure.centralindia', 'azure.eastasia', 'azure.japaneast', 'azure.jioindiawest', 'azure.koreacentral', 'azure.canadacentral', 'azure.francecentral', 'azure.germanywestcentral', 'azure.norwayeast', 'azure.switzerlandnorth', 'azure.uaenorth', 'azure.brazilsouth', 'azure.centralusstage', 'azure.eastusstage', 'azure.eastus2stage', 'azure.northcentralusstage', 'azure.southcentralusstage', 'azure.westusstage', 'azure.westus2stage', 'azure.asia', 'azure.asiapacific', 'azure.australia', 'azure.brazil', 'azure.canada', 'azure.europe', 'azure.global', 'azure.india', 'azure.japan', 'azure.uk', 'azure.unitedstates', 'azure.eastasiastage', 'azure.southeastasiastage', 'azure.centraluseuap', 'azure.eastus2euap', 'azure.westcentralus', 'azure.southafricawest', 'azure.australiacentral', 'azure.australiacentral2', 'azure.australiasoutheast', 'azure.japanwest', 'azure.jioindiacentral', 'azure.koreasouth', 'azure.southindia', 'azure.westindia', 'azure.canadaeast', 'azure.francesouth', 'azure.germanynorth', 'azure.norwaywest', 'azure.swedensouth', 'azure.switzerlandwest', 'azure.ukwest', 'azure.uaecentral', 'azure.brazilsoutheast'))
organization_url
  URL host invalid, top level domain required (type=value_error.url.host)
```

</details>
<br>

> We can use the validation functions provided `pangeo-forge-orchestrator.validation` to setup CI tests for [pangeo-forge/bakery-database](https://github.com/pangeo-forge/bakery-database), and edit the database there to conform to the spec.
>
> Currently the validators in `pangeo_forge_orchestrator.validation` are only exposed via the Python API. We may want to add them to the CLI in a future PR.

## What does work 🎉

In the interim, and because it's easy to imagine users wanting to interface with Bakeries not (or not yet) in the official database, there is an option to provide a path to a custom Bakery database. This [`make_bakery_yaml.py`](https://gist.github.com/cisaacstern/7a5273c892f3b3854b02512e398c2f8e), for example, writes a valid database file called `test-bakery.yaml` which describes access to the Pangeo Forge Open Storage Network (OSN) target. By passing this file to the CLI, we can now do

```zsh
➜ pangeo-forge bakery ls --custom-db test-bakery.yaml

['org.test-osn.bakery.aws.us-west-2']
```
... and get the indenteded output: a list of Bakery names present in the database.

> As you can see here, pydantic doesn't know that `test-osn.org` is not a real organization url, only that it is theoretically an `HttpUrl` (i.e. ends with a TLD). For more on this, see the section on `BakeryName` in {doc}`new_pydantic_types`.

Now if we want to see details about a Bakery from our database, we just pass its name as an arguement:

```zsh
➜ pangeo-forge bakery ls --custom-db test-bakery.yaml --bakery-id 'org.test-osn.bakery.aws.us-west-2'
```
> (TODO: `--bakery-id` here should be `--bakery-name`, for consistency.)

<details>

<summary> Output details </summary>

```python
{
    'cluster': None,
    'region': 'aws.us-west-2',
    'targets': {
        'osn': {
            'description': 'Open Storage Network (OSN) bucket',
            'private': {
                'prefix': 'Pangeo/pangeo-forge',
                'protocol': 's3',
                'storage_options': {
                    'client_kwargs': {'endpoint_url': 'https://ncsa.osn.xsede.org'},
                    'default_cache_type': 'none',
                    'default_fill_cache': False,
                    'key': '{OSN_KEY}',
                    'secret': '{OSN_SECRET}',
                    'use_listings_cache': False
                }
            },
            'public': {
                'prefix': 'Pangeo/pangeo-forge',
                'protocol': 's3',
                'storage_options': {'anon': True, 'client_kwargs': {'endpoint_url': 'https://ncsa.osn.xsede.org'}}
            },
            'region': 'aws.us-west-2'
        }
    }
}

```

</details>
<br>


There are many reasons why a user would want to review these Bakery details, but this information is also meant for consumption by downstream processes, including cataloging. To build a STAC Item for a given dataset (which has already been built to a Bakery storage target), we simply pass the Bakery name along with the dataset's 5-digit run identifier to the `make-stac-item` command:

```zsh
➜ pangeo-forge catalog make-stac-item 'org.test-osn.bakery.aws.us-west-2' 00000 --bakery-database-path test-bakery.yaml
```

<details>

<summary> Output details </summary>

{
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
            'lon': {'type': 'spatial', 'axis': 'x', 'description': 'Longitude', 'extent': [0.125, 359.875], 'step': 0.25},
            'lat': {'type': 'spatial', 'axis': 'y', 'description': 'Latitude', 'extent': [-89.875, 89.875], 'step': 0.25}
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
                'attrs': {'long_name': 'Sea ice concentration', 'units': '%', 'valid_max': 100, 'valid_min': 0}
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
        'coordinates': [[[89.875, 0.125], [89.875, 359.875], [-89.875, 359.875], [-89.875, 0.125], [89.875, 0.125]]]
    },
    'links': [],
    'assets': {
        'pangeo-forge-feedstock': {
            'href': 'https://github.com/pangeo-forge/noaa-oisst-avhrr-only-feedstock/tree/v1.0',
            'type': '',
            'title': 'Pangeo Forge Feedstock (GitHub repository) for noaa-oisst-avhrr-only-feedstock@1.0'
        },
        'jupyter-notebook-example-https': {'href': '_', 'type': '', 'title': ''},
        'jupyter-notebook-example-s3': {'href': '_', 'type': '', 'title': ''},
        'zarr-s3': {
            'href': 's3://Pangeo/pangeo-forge/noaa_oisst/v2.1-avhrr.zarr',
            'type': 'application/vnd+zarr',
            'title': 'NOAA Optimum Interpolated SST - S3 File System Zarr root',
            'description': 'S3 File System Zarr root for analysis-ready Zarr datasets derived from NOAA OISST NetCDF',
            'xarray:storage_options': {'anon': True, 'client_kwargs': {'endpoint_url': 'https://ncsa.osn.xsede.org'}},
            'xarray:open_kwargs': {'consolidated': True},
            'roles': ['data', 'zarr', 's3']
        },
        'zarr-https': {
            'href': 's3://Pangeo/pangeo-forge/noaa_oisst/v2.1-avhrr.zarr',
            'type': 'application/vnd+zarr',
            'title': 'NOAA Optimum Interpolated SST - HTTPS File System Zarr root',
            'description': 'HTTPS File System Zarr root for analysis-ready Zarr datasets derived from NOAA OISST NetCDF',
            'xarray:storage_options': None,
            'xarray:open_kwargs': {'consolidated': True},
            'roles': ['data', 'zarr', 'https']
        }
    },
    'bbox': [-89.875, 0.125, 89.875, 359.875],
    'stac_extensions': ['https://stac-extensions.github.io/datacube/v2.0.0/schema.json']
}


</details>
<br>

Metadata for this Item which exists in the dataset itself is extracted using [https://github.com/TomAugspurger/xstac](https://github.com/TomAugspurger/xstac).

The `make-stac-item` command's `--to-file` flag provides functionality for writing the resulting STAC Item either to local disk or to a specified path in the Bakery storage target. The `--execute-notebooks` flag executes example notebooks using [papermill](https://papermill.readthedocs.io/en/latest/). There is also a draft feature in `pangeo_forge_orchestrator.notebook` for POST the executed notebooks to GitHub Gist, but this is currently [one of the gaps in testing](https://app.codecov.io/gh/pangeo-forge/pangeo-forge-orchestrator/blob/620989215c8d191d55c3080d403d6454a895230b/pangeo_forge_orchestrator/notebook.py).
