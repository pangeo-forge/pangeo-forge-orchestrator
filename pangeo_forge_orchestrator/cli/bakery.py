from typing import Optional

import typer
from rich import print
from rich.table import Table

from ..metadata import BakeryMetadata

app = typer.Typer()


@app.command()
def ls(
    extra_bakery_yaml: Optional[str] = None,
    bakery_id: Optional[str] = None,
    view: str = "general-info",
    feedstock_id: Optional[str] = None,
):
    """
    List available bakeries and associated build-logs.
    """

    bakery_meta = BakeryMetadata(bakery_id=bakery_id, extra_bakery_yaml=extra_bakery_yaml)

    if not bakery_id:
        print(list(bakery_meta.bakery_dict))
    elif view == "general-info":
        print(bakery_meta.bakery_dict[bakery_id])
    elif view == "build-logs":
        if not feedstock_id:
            logs = bakery_meta.build_logs
            table = _table_from_bakery_logs(logs)
            print(table)
        else:
            logs = bakery_meta.filter_logs(feedstock_id)
            table = _table_from_bakery_logs(logs)
            print(table)


def _table_from_bakery_logs(logs: dict):
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
        [
            k,
            logs[k]["timestamp"],
            logs[k]["feedstock"],
            logs[k]["recipe"],
            logs[k]["path"],
        ]
        for k in reversed(logs.keys())
    ]
    for r in rows:
        table.add_row(*r)
    return table
