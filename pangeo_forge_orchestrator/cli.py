from typing import Optional

# mypy says stubs not installed but they are... hmm...
import requests  # type: ignore
import typer

from .models import HeroCreate

cli = typer.Typer()


@cli.command()
def create_hero(
    name: str = typer.Option(...),
    secret_name: str = typer.Option(...),
    age: Optional[int] = None,
    base_url: str = "http://127.0.0.1:8000",
):
    """
    """
    hero = HeroCreate(name=name, secret_name=secret_name, age=age)
    response = requests.post(f"{base_url}/heroes/", json=hero.dict())
    typer.echo(response.json())


@cli.command()
def read_hero():
    pass


if __name__ == "__main__":
    cli()
