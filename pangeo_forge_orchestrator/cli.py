import json
import os

import typer

from .client import Client
from .models import HeroCreate

cli = typer.Typer()
client = Client(base_url=os.environ["PANGEO_FORGE_DATABASE_URL"])


@cli.command()
def create_hero(hero: str):
    """
    hero: json string
    """
    hero = HeroCreate(**json.loads(hero))
    response = client.create_hero(hero=hero)
    typer.echo(response.json())


@cli.command()
def read_hero():
    pass


if __name__ == "__main__":
    cli()
