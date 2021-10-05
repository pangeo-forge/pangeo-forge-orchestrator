import typer

from . import bakery
from .catalog import catalog

app = typer.Typer()

app.add_typer(bakery.app, name="bakery")
app.add_typer(catalog.app, name="catalog")


@app.command()
def lint(path: str):
    """
    Lint a recipe
    """
    typer.echo(f"Linting recipe {path}")
