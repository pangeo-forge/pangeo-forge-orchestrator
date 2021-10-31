import json
import os
from dataclasses import dataclass
from pathlib import Path

import papermill as pm
import requests  # type: ignore

parent = Path(__file__).absolute().parent


@dataclass
class ExecuteNotebook:

    feedstock_id: str
    template_dir: str = f"{parent}/templates/jupyter"
    nbviewer_url_base: str = "https://nbviewer.org/gist/cisaacstern"  # change to Pangeo Forge Bot

    def make_template_path(self, endpoint):
        endpoint = endpoint if endpoint != "http" else "https"  # TODO: better solution for tests?
        return f"{endpoint}_loading_template.ipynb"

    def make_filename(self, endpoint):
        return f"{self.feedstock_id}_via_{endpoint}.ipynb"

    def execute(self, endpoint, stac_item_path):
        template_path = f"{self.template_dir}/{self.make_template_path(endpoint)}"
        filename = self.make_filename(endpoint)
        parameters = dict(path=stac_item_path)
        pm.execute_notebook(template_path, filename, parameters=parameters)
        return filename

    def post_gist(self, local_path, url="https://api.github.com/gists"):
        if "GITHUB_API_TOKEN" not in os.environ.keys():
            raise ValueError(
                "Environment variable 'GITHUB_API_TOKEN' required for Gist API authentication."
            )
        with open(local_path) as f:
            content = json.loads(f.read())

        path_split = local_path.split("_via_")
        feedstock_id, protocol = path_split[0], path_split[1].split(".")[0]
        payload = {
            "description": f"An example notebook for loading {feedstock_id} via {protocol}.",
            "public": True,
            "files": {local_path: {"content": json.dumps(content)}},
        }
        r = requests.post(
            url=url,
            headers={"Authorization": f"token {os.environ['GITHUB_API_TOKEN']}"},
            params={"scope": "gist"},
            data=json.dumps(payload),
        )
        # uncomment for debugging (move to logger.DEBUG later)
        # print("Gist POST returned status code", r.status_code)
        # print("url", r.url)
        # print("text", r.text)
        gist_id = json.loads(r.text)["id"]
        print(f"{local_path} POSTed as Gist with ID {gist_id}")
        return f"{self.nbviewer_url_base}/{gist_id}"
