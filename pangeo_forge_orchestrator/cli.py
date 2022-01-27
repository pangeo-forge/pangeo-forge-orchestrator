import json

import typer

from .client import Client

cli = typer.Typer(name="Pangeo Forge")
db = typer.Typer()

top_endpoint = "A top level endpoint, enclosed in forward slashes, e.g. '/my_endpoint/'."
specific_endpoint = "A unique entry endpoint concluding with an integer id, e.g. '/my_endpoint/1'."
json_help = "A JSON string, created via with Python's ``json.dumps`` method, for example."


def get_client(server: str, api_key: str) -> Client:
    # Putting this in a function means that the environment variable is checked
    # at evaluation time rather than import time.
    return Client(base_url=server, api_key=(api_key or None))


@db.callback()
def common(
    ctx: typer.Context,
    server: str = typer.Option(
        "https://api.pangeo-forge.org",
        envvar="PANGEO_FORGE_SERVER",
        help="Pangeo Forge API server URL.",
    ),
    api_key: str = typer.Option("", envvar="PANGEO_FORGE_API_KEY", help="Pangeo Forge API Key"),
):
    """Common Entry Point"""
    ctx.obj = get_client(server, api_key)


@db.command()
def post(
    ctx: typer.Context,
    endpoint: str = typer.Argument(..., help=top_endpoint),
    data: str = typer.Argument(..., help=json_help),
):
    """Add new entries to the database."""
    response = ctx.obj.post(endpoint=endpoint, json=json.loads(data))
    typer.echo(response.text)


@db.command()
def get(
    ctx: typer.Context,
    endpoint: str = typer.Argument(
        ...,
        help=(
            f"Either {top_endpoint.lower()} Or {specific_endpoint.lower()} If the former, returns "
            "list of all entries in corresponding table. If the latter, returns single table entry."
        ),
    ),
):
    """Read entries from the database."""
    response = ctx.obj.get(endpoint=endpoint)
    typer.echo(response.text)


@db.command()
def patch(
    ctx: typer.Context,
    endpoint: str = typer.Argument(..., help=specific_endpoint),
    data: str = typer.Argument(..., help=json_help),
):
    """Update entries in the database."""
    response = ctx.obj.patch(endpoint=endpoint, json=json.loads(data))
    typer.echo(response.text)


@db.command()
def delete(ctx: typer.Context, endpoint: str = typer.Argument(..., help=specific_endpoint)):
    """Delete entries from the database."""
    response = ctx.obj.delete(endpoint=endpoint)
    typer.echo(response.text)


cli.add_typer(db, name="database")


if __name__ == "__main__":  # pragma: no cover
    cli()
