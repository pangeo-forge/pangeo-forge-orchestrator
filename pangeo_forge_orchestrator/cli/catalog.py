import typer

from ..catalog import generate

app = typer.Typer()


@app.command()
def make_stac_item(
    bakery_id: str,
    run_id: str,
    to_file: str = None,
    execute_notebooks: bool = False,
):
    """
    Generate a STAC Item for a `bakery_id` + `run_id` pair.
    """
    generate(bakery_id, run_id, to_file, execute_notebooks)
