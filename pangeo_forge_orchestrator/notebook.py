from dataclasses import dataclass
from pathlib import Path

import papermill as pm

parent = Path(__file__).absolute().parent


@dataclass
class ExecuteNotebook:

    template_dir: str = f"{parent}/templates/jupyter"

    def make_template_path(self, endpoint):
        return f"{endpoint}_loading_template.ipynb"

    def make_outpath(self, endpoint, feedstock_id):
        return f"{feedstock_id}_via_{endpoint}.ipynb"

    def execute(self, endpoint, feedstock_id):
        template_path = f"{self.template_dir}/{self.make_template_path(endpoint)}"
        outpath = self.make_outpath(endpoint, feedstock_id)
        parameters = dict(path=f"{feedstock_id}.json")
        pm.execute_notebook(template_path, outpath, parameters=parameters)
