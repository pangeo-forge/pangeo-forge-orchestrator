import typer

from ..catalog import generate

app = typer.Typer()


@app.command()
def make_stac_item(bakery_id: str, run_id: str, output: str = "stdout"):
    """
    Generate a STAC Item for a `bakery_id` + `run_id` pair.
    """
    generate(bakery_id, run_id, output)
