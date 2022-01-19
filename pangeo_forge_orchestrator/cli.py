import ast
import os

import typer

from .client import Client

cli = typer.Typer()
db = typer.Typer()

top_endpoint = "A top level endpoint, enclosed in forward slashes, e.g. '/my_endpoint/'."
specific_endpoint = "A unique entry endpoint concluding with an integer id, e.g. '/my_endpoint/1'."
json_help = "A JSON string, created via with Python's ``json.dumps`` method, for example."


def get_client():
    # Putting this in a function means that the environment variable is checked
    # at evaluation time rather than import time.
    return Client(base_url=os.environ["PANGEO_FORGE_DATABASE_URL"])


@db.command()
def post(
    endpoint: str = typer.Argument(..., help=top_endpoint),
    json: str = typer.Argument(..., help=json_help),
):
    """Add new entries to the database."""
    as_dict = ast.literal_eval(json)
    response = get_client().post(endpoint=endpoint, json=as_dict)
    typer.echo(response.text)


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
    response = get_client().get(endpoint=endpoint)
    typer.echo(response.text)


@db.command()
def patch(
    endpoint: str = typer.Argument(..., help=specific_endpoint),
    json: str = typer.Argument(..., help=json_help),
):
    """Update entries in the database."""
    as_dict = ast.literal_eval(json)
    response = get_client().patch(endpoint=endpoint, json=as_dict)
    typer.echo(response.text)


@db.command()
def delete(endpoint: str = typer.Argument(..., help=specific_endpoint)):
    """Delete entries from the database."""
    response = get_client().delete(endpoint=endpoint)
    typer.echo(response.text)


cli.add_typer(db, name="database")


if __name__ == "__main__":  # pragma: no cover
    cli()
