from typing import Optional

import typer
from rich import print
from rich.table import Table

from ..utils import BakeryMetadata

app = typer.Typer()


@app.command()
def ls(
    bakery_id: Optional[str] = None,
    view: str = "general-info",
    feedstock_name: Optional[str] = None,
):
    """
    List available bakeries and associated build-logs.
    """

    bakery_meta = BakeryMetadata(bakery_id=bakery_id)

    if not bakery_id:
        print(list(bakery_meta.bakery_dict))
    elif view == "general-info":
        print(bakery_meta.bakery_dict[bakery_id])
    elif view == "build-logs":

        table = Table()
        table.add_column("Run ID", style="magenta")
        table.add_column("Timestamp", style="blue")
        table.add_column("Feedstock", style="green")
        table.add_column("Recipe", style="red")
        table.add_column("Path", style="cyan")

        logs = bakery_meta.build_logs
        ids = list(logs.keys())
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
        if not feedstock_name:
            for r in rows:
                table.add_row(*r)
            print(table)
        else:
            rows = [r for r in rows if feedstock_name in r[2]]
            for r in rows:
                table.add_row(*r)
            print(table)
