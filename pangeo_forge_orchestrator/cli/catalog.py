from typing import List, Optional

import typer

from ..catalog import generate

app = typer.Typer()


@app.command()
def make_stac_item(
    bakery_name: str,  # TODO: Provide stricter type from `..meta_types.bakery` here
    run_id: str,  # TODO: same as above
    bakery_database_path: Optional[str] = None,
    # bakery_stac_relative_path: Optional[str] = None,
    feedstock_metadata_url_base: Optional[str] = None,
    endpoints: Optional[List[str]] = None,
    print_result: bool = True,
    to_file: Optional[bool] = False,
):
    """
    Generate a STAC Item for a `bakery_name` + `run_id` pair.
    """
    kw = dict(bakery_name=bakery_name, run_id=run_id, print_result=print_result, to_file=to_file,)
    if bakery_database_path:
        kw.update(dict(bakery_database_path=bakery_database_path))
    if feedstock_metadata_url_base:
        kw.update(dict(feedstock_metadata_url_base=feedstock_metadata_url_base))
    if endpoints:
        kw.update(dict(endpoints=endpoints))
    generate(**kw)
