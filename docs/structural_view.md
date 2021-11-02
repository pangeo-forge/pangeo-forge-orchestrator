# Architecture

Here's what we have so far (with `__init__.py`s omitted, for conciseness). Note that most of this is new code, with the exception of `meta_types/*` which were merged from [pangeo_forge_prefect/meta_types](https://github.com/pangeo-forge/pangeo-forge-prefect/tree/master/pangeo_forge_prefect/meta_types). Within that subdirectory, I've thus far only updated `meta_types/bakery.py` (details of those changes described in {doc}`new_pydantic_types`).

```zsh
pangeo_forge_orchestrator
├── api
│   └── # TODO: FastAPI implementation
├── automation
│   └── # TODO: Merge existing pangeo_forge_prefect/flow_manager.py etc. here.
├── catalog.py  # cataloging utils
├── cli
│   ├── bakery.py
│   ├── catalog.py
│   ├── feedstock.py
│   ├── main.py  # CLI entrypoint
│   └── recipe.py
├── components.py  # contains `Bakery` and `FeedstockMetadata` interfaces
├── meta_types
│   ├── bakery.py
│   ├── meta.py      # `meta.py` and `versions.py` currently remain unchanged
│   └── versions.py  # ... from `pangeo_forge_prefect/meta_types`
├── notebook.py  # automated notebook execution utils
├── templates
│   ├── jupyter
│   │   ├── https_loading_template.ipynb
│   │   └── s3_loading_template.ipynb
│   └── stac
│       └── item_template.json
└── validation
    ├── exceptions.py
    └── validate_bakery_database.py
```

Almost anything you'd want to do within `pangeo-forge-orchestrator` requires interfacing with a particular Pangeo Forge Bakery and/or Feedstock. These interfaces are housed in the `components.py` module. The Bakery and Feedstock interfaces themselves rely on the aforementioned `meta_types` to parse their attributes (or "fields", in pydantic parlance) into standardize forms.

## `Bakery` and `FeedstockMetadata` APIs

```{eval-rst}
.. autoclass:: pangeo_forge_orchestrator.components.Bakery
    :members:
```

```{eval-rst}
.. autoclass:: pangeo_forge_orchestrator.components.FeedstockMetadata
    :members:
```
