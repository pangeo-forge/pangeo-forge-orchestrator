from typing import Optional

import typer
from rich import print
from rich.table import Table

from ..interfaces import Bakery
from ..meta_types.bakery import bakery_database_from_dict
from ..validation.validate_bakery_database import open_bakery_database_yaml

app = typer.Typer()


@app.command()
def ls(
    bakery_name: Optional[str] = None,
    view: str = "general-info",
    feedstock_id: Optional[str] = None,
    bakery_database_path: Optional[str] = typer.Option(None, envvar="PANGEO_FORGE_BAKERY_DATABASE"),
) -> None:
    """
    List available bakeries and associated build-logs.
    """
    bakery_database_dict = open_bakery_database_yaml(bakery_database_path)
    # validate against `..meta_types.bakery.BakeryDatabase`
    _ = bakery_database_from_dict(bakery_database_dict)

    if not bakery_name:
        print([name for name in bakery_database_dict.keys()])  # type: ignore
    else:
        kw = dict(database_path=bakery_database_path) if bakery_database_path else {}
        bakery = Bakery(bakery_name, **kw)  # type: ignore
        if view == "general-info":
            print(bakery_database_dict[bakery_name])  # type: ignore
        elif view == "build-logs":
            if not feedstock_id:
                logs = bakery.build_logs.logs  # type: ignore
                table = _table_from_bakery_logs(logs)
                print(table)
            else:
                logs = bakery.filter_logs(feedstock_id)
                table = _table_from_bakery_logs(logs)
                print(table)


def _table_from_bakery_logs(logs: dict) -> Table:
    """
    """
    table = Table()
    columns = {
        "Run ID": "magenta",
        "Timestamp": "blue",
        "Feedstock": "green",
        "Recipe": "red",
        "Path": "cyan",
    }
    for k, v in columns.items():
        table.add_column(k, style=v)
    rows = [
        [str(k), str(logs[k].timestamp), logs[k].feedstock, logs[k].recipe, logs[k].path]
        for k in logs.keys()
    ]
    for r in rows:
        table.add_row(*r)
    return table
