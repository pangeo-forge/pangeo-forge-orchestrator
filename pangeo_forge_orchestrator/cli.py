from typing import Optional

# mypy says stubs not installed but they are... hmm...
import requests  # type: ignore
import typer

from .models import HeroCreate

cli = typer.Typer()

URL = "http://127.0.0.1:8000"


@cli.command()
def create_hero(
    name: str = typer.Option(...), secret_name: str = typer.Option(...), age: Optional[int] = None,
):
    """
    """
    h = HeroCreate(name=name, secret_name=secret_name, age=age)
    r = requests.post(f"{URL}/heroes/", json=h.dict())
    typer.echo(f"{r.json()}")


@cli.command()
def read_hero():
    pass


if __name__ == "__main__":
    cli()
