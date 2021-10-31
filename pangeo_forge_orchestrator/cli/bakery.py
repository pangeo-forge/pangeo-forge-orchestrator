from typing import Optional

import typer
from rich import print
from rich.table import Table

from ..components import Bakery
from ..meta_types.bakery import BakeryDatabase

app = typer.Typer()


@app.command()
def ls(
    custom_db: Optional[str] = None,
    bakery_id: Optional[str] = None,
    view: str = "general-info",
    feedstock_id: Optional[str] = None,
):
    """
    List available bakeries and associated build-logs.
    """
    kw = dict(path=custom_db) if custom_db else {}

    if not bakery_id:
        bakery_db = BakeryDatabase(**kw)
        print(list(bakery_db.bakeries))  # type: ignore
    else:
        bakery_meta = Bakery(bakery_id, **kw)
        if view == "general-info":
            print(bakery_meta.bakeries[bakery_id])  # type: ignore
        elif view == "build-logs":
            if not feedstock_id:
                logs = bakery_meta.build_logs.logs  # type: ignore
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
        [k, str(logs[k].timestamp), logs[k].feedstock, logs[k].recipe, logs[k].path]
        for k in reversed(logs.keys())
    ]
    for r in rows:
        table.add_row(*r)
    return table
