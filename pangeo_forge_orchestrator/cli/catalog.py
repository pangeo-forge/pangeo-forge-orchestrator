from typing import Optional

import typer

from ..catalog import generate

app = typer.Typer()


@app.command()
def make_stac_item(
    bakery_name: str,  # TODO: Provide stricter type from `..meta_types.bakery` here
    run_id: int,
    print_result: bool = True,
    to_file: Optional[bool] = False,
    feedstock_metadata_path_base: Optional[str] = typer.Option(
        None, envvar="PANGEO_FORGE_FEEDSTOCK_METADATA_PATH_BASE",
    ),
    feedstock_metadata_path_format: Optional[str] = typer.Option(
        None, envvar="PANGEO_FORGE_FEEDSTOCK_METADATA_PATH_FORMAT",
    ),
    bakery_database_path: Optional[str] = typer.Option(None, envvar="PANGEO_FORGE_BAKERY_DATABASE"),
):
    """
    Generate a STAC Item for a `bakery_name` + `run_id` pair.
    """

    def prune_dict(d):
        return {k: v for k, v in d.items() if v is not None}

    bakery_kwargs = prune_dict(dict(database_path=bakery_database_path))

    feedstock_kwargs = prune_dict(
        dict(
            metadata_path_base=feedstock_metadata_path_base,
            metadata_path_format=feedstock_metadata_path_format,
        )
    )
    kw = dict(
        bakery_name=bakery_name,
        run_id=run_id,
        print_result=print_result,
        to_file=to_file,
        bakery_kwargs=bakery_kwargs,
        feedstock_kwargs=feedstock_kwargs,
    )
    generate(**kw)  # type: ignore
