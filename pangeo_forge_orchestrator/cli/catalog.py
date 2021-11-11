from typing import Optional

import typer

from ..catalog import generate

app = typer.Typer()


@app.command()
def make_stac_item(
    bakery_name: str,  # TODO: Provide stricter type from `..meta_types.bakery` here
    run_id: int,
    # bakery_stac_relative_path: Optional[str] = None,
    feedstock_metadata_url_base: Optional[str] = None,
    print_result: bool = True,
    to_file: Optional[bool] = False,
    bakery_database_path: Optional[str] = typer.Option(None, envvar="PANGEO_FORGE_BAKERY_DATABASE"),
):
    """
    Generate a STAC Item for a `bakery_name` + `run_id` pair.
    """
    kw = dict(bakery_name=bakery_name, run_id=run_id, print_result=print_result, to_file=to_file,)
    if bakery_database_path:
        kw.update(dict(bakery_database_path=bakery_database_path))
    if feedstock_metadata_url_base:
        kw.update(dict(feedstock_metadata_url_base=feedstock_metadata_url_base))
    generate(**kw)  # type: ignore
