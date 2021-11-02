# New pydantic types

In updating `meta_types/bakery.py` (as mentioned in {doc}`structural_view`), `pangeo-forge-orchestrator` aims to implement Pydantic-based input validation with the lightest touch possible for each input type. The types were initially implemented as Python dataclasses, so for many of them, the edit was simply to use `pydantic.dataclasses` as a drop-in replacement (perhaps in combination with stricter type hints). In addition, three new dataclasses, two new Models, and some regex-constrained type functions are defined; these are described below.

## `BakeryName`

This dataclass validates a string against the [Bakery naming scheme defined in the Bakery database ADR](https://github.com/pangeo-forge/roadmap/blob/master/doc/adr/0004-use-yaml-file-for-bakery-database.md#bakery-name). As I understand it, the stipulation to "follow [java package syntax](https://docs.oracle.com/javase/tutorial/java/package/namingpkgs.html) to ensure unique bakery names" means that these names should all begin with a reversed organization url. Therefore, I'm making the assumption (reflected in this dataclass's type hinting) that un-reversing this portion of the Bakery name should yield a valid `pydantic.HttpUrl`. (More on this in {doc}`use_guide`.) In addition, following the ADR, an acceptable Bakery name input string must conclude with `".bakery.{region}"` where region conforms to an `"{provider}.{region}"` format.

```{eval-rst}
.. autoclass:: pangeo_forge_orchestrator.meta_types.bakery.BakeryName
    :members:
```

## `RunRecord`

> This type (along with the next one, `BuildLogs`) provide the necessary link, mentioned in {doc}`motivation`, between datasets in a Bakery target and the Feedstocks from which they were built. They are new concepts for Pangeo Forge and certainly merit their own ADR. After we move through this PR (assuming we agree that some version of these concepts are useful), we can work on an ADR for them.

This is a container for metadata describing the execution of a Pangeo Forge Recipe, including:
- **timestamp**: The datetime at which the execution took place (not sure if this should be start, end, or maybe tuple of both).
- **feedstock**: The name of the feedstock (including version). For this PR, I'm provisionally using the format `"{feedstock_name}@{major_version}.{minor_version}"`.
- **recipe**: The name of the Python object within the Feedstock's `recipe.py` module which was used to build the dataset. In the case of a single-recipe module, this is the name of a `pangeo_forge_recipes.recipes` class instance (and therefore needs to be a valid Python identifier). In the case of a [`dict_object`](https://github.com/pangeo-forge/roadmap/blob/master/doc/adr/0002-use-meta-yaml-to-track-feedstock-metadata.md#recipes-section), this would follow the established convention for the `meta.yaml`: i.e., `"{dict_name}:{dict_key}"`.
- **path**: The relative path to the dataset within the Bakery storage target.

```{eval-rst}
.. autoclass:: pangeo_forge_orchestrator.meta_types.bakery.RunRecord
    :members:
```


## `BuildLogs`

This is a mapping between an execution run identifier and a `RunRecord`. Provisionally, I'm specifying a run identifier as a (five digit) integer string, i.e. `"00000"`, `"00001"` etc. The idea here is that these values would be sequentially assigned to each dataset as they are built to a given Bakery storage target. (And each Bakery target would keep its own tally.) There are other identifiers (i.e. the dataset path) which will be unique within a given Bakery storage target, but the idea here is to provide a short string for passing as a command line argument (an example of this is provided in the {doc}`use_guide`). Maybe there are alternative identifiers worth considering here.

> Currently, the `pangeo_forge_orchestrator.components.Bakery` object assumes that a `build_logs.json` (with entries parsable into `BuildLogs` objects) will exist at the Bakery target's root path. By opening and parsing this JSON, the `Bakery` instance knows exactly what dataset paths exist at the target and what Feedstocks they are tied to. In the future, these records could be ingested into a database instead of, or in addition to, keeping a copy in the Bakery target.

```{eval-rst}
.. autoclass:: pangeo_forge_orchestrator.meta_types.bakery.BuildLogs
    :members:
```

## Why is `StorageOptions` a Model?

The Bakery database ADR [defines a `storage_options` field](https://github.com/pangeo-forge/roadmap/blob/master/doc/adr/0004-use-yaml-file-for-bakery-database.md#storage-options) for Bakery target access parameters. The reason we're defining the Python container for these options as a pydantic Model, rather than a dataclass, is for the [`.dict(exclude_none=True)` method](https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict), which allows us to define arbitrary numbers of optional type-checked fields for this object, but also succinctly export kwargs dictionaries representing only those fields which have been set on a given instance.

```{eval-rst}
.. autoclass:: pangeo_forge_orchestrator.meta_types.bakery.StorageOptions
    :members:
```


## ... and what about `BakeryDatabase`?

The new `BakeryDatabase` object is a Model (instead of a dataclass) because we want to take advantage of Model features for `pangeo_forge_orchestrator.components.Bakery`, and it seemed to make sense to have `Bakery` inherit from `BakeryDatabase`.

```{eval-rst}
.. autoclass:: pangeo_forge_orchestrator.meta_types.bakery.BakeryDatabase
    :members:
```

## What's with those regexes?

There are certain string values (such as the Feedstock name, etc.) which we definitely want to ensure conform to a specified format, but for which it seemed excessive to define an entire class for. For [these cases](https://github.com/pangeo-forge/pangeo-forge-orchestrator/blob/620989215c8d191d55c3080d403d6454a895230b/pangeo_forge_orchestrator/meta_types/bakery.py#L110-L121), I opted to use pydantic's [Constrained Type function, `constr`](https://pydantic-docs.helpmanual.io/usage/types/#constrained-types). I (and I think most people) don't find regular expressions especially readable, so I wrote explanatory comments for each of these cases.

## Full diff

And finally, here's [the full diff](https://github.com/pangeo-forge/pangeo-forge-orchestrator/compare/de36c30070f249136a5eb3c0f54144f3eaafb428..620989215c8d191d55c3080d403d6454a895230b#diff-374b3112607d6019e80fa96dff3aec0f9159e803faf62a96ef35330f308bff9b) between Sean's existing types, and those proposed in this PR.
