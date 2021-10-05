import json
from typing import Optional

import fsspec
import typer
import yaml
from rich import print
from rich.table import Table

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
    bakery_database = (
        "https://raw.githubusercontent.com/pangeo-forge/bakery-database/main/bakeries.yaml"
    )
    with fsspec.open(bakery_database) as f:
        read_yaml = f.read()
        bakery_dict = yaml.safe_load(read_yaml)

        # add an additional mock bakery for testing purposes
        osn = dict(
            anon=True,
            client_kwargs={'endpoint_url': 'https://ncsa.osn.xsede.org'},
            root_path="s3://Pangeo/pangeo-forge",
        )
        bakery_dict.update({"great_bakery": {"targets": {"osn": osn}}})

        if not bakery_id:
            print(list(bakery_dict))
        elif view == "general-info":
            print(bakery_dict[bakery_id])
        elif view == "build-logs":

            table = Table()
            table.add_column("Run ID", style="magenta")
            table.add_column("Timestamp", style="blue")
            table.add_column("Feedstock", style="green")
            table.add_column("Recipe", style="red")
            table.add_column("Path", style="cyan")

            k = list(bakery_dict[bakery_id]["targets"].keys())[0]
            target = bakery_dict[bakery_id]["targets"][k]
            kwargs = {k: v for k, v in target.items() if k != "root_path"}

            with fsspec.open(f"{target['root_path']}/build-logs.json", **kwargs) as f2:
                read_json = f2.read()
                logs = json.loads(read_json)
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
