import typer

app = typer.Typer()


@app.command()
def lint(path: str):
    """
    Lint a recipe
    """
    typer.echo(f"Linting recipe {path}")
