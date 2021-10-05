import typer

app = typer.Typer()

@app.command()
def make_stac_item(path: str):
    """
    Generate a STAC Item for the specified path.
    """
    typer.echo(f"Making a STAC Item for {path}")
