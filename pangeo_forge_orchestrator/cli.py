import ast
import os

import typer

from .client import Client

cli = typer.Typer()
client = Client(base_url=os.environ["PANGEO_FORGE_DATABASE_URL"])


@cli.command()
def post(endpoint: str, json: str):
    """
    :param json: JSON string as returned by passing a valid request dict to ``json.dumps``.
    """
    as_dict = ast.literal_eval(json)
    response = client.post(endpoint=endpoint, json=as_dict)
    typer.echo(response.json())


@cli.command()
def read_hero():
    pass


if __name__ == "__main__":
    cli()
