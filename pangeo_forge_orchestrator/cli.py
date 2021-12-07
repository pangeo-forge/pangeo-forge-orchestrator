import ast
import os

import typer

from .client import Client

cli = typer.Typer()
db = typer.Typer()
client = Client(base_url=os.environ["PANGEO_FORGE_DATABASE_URL"])

top_endpoint = "A top level endpoint, enclosed in forward slashes, e.g. '/my_endpoint/'."
specific_endpoint = "An entry endpoint concluding with an integer id, e.g. '/my_endpoint/1'."
json_help = "A JSON string, created via with Python's ``json.dumps`` method, for example."


@db.command()
def post(
    endpoint: str = typer.Argument(..., help=top_endpoint),
    json: str = typer.Argument(..., help=json_help),
):
    """Add new entries to the database."""
    as_dict = ast.literal_eval(json)
    response = client.post(endpoint=endpoint, json=as_dict)
    typer.echo(response.json())


@db.command()
def get(
    endpoint: str = typer.Argument(
        ...,
        help=(
            f"Either {top_endpoint.lower()} Or {specific_endpoint.lower()} If the former, returns "
            "list of all entries in corresponding table. If the latter, returns single table entry."
        ),
    )
):
    """Read entries from the database."""
    response = client.get(endpoint=endpoint)
    typer.echo(response.json())


@db.command()
def patch(
    endpoint: str = typer.Argument(..., help=specific_endpoint),
    json: str = typer.Argument(..., help=json_help),
):
    """Update entries in the database."""
    as_dict = ast.literal_eval(json)
    response = client.patch(endpoint=endpoint, json=as_dict)
    typer.echo(response.json())


@db.command()
def delete(endpoint: str = typer.Argument(..., help=specific_endpoint)):
    """Delete entries from the database."""
    response = client.delete(endpoint=endpoint)
    typer.echo(response.json())


cli.add_typer(db, name="database")


if __name__ == "__main__":
    cli()
