import typer
from rich import print

from ..catalog import generate

app = typer.Typer()

@app.command()
def make_stac_item(bakery_id: str, run_id: str):
    """
    Generate a STAC Item for a `bakery_id` + `run_id` pair.
    """
    generate(bakery_id=bakery_id, run_id=run_id)
