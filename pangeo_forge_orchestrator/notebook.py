from dataclasses import dataclass
from pathlib import Path

import papermill as pm

parent = Path(__file__).absolute().parent


@dataclass
class ExecuteNotebook:

    feedstock_id: str
    template_dir: str = f"{parent}/templates/jupyter"

    def make_template_path(self, endpoint):
        return f"{endpoint}_loading_template.ipynb"

    def make_outpath(self, endpoint):
        return f"{self.feedstock_id}_via_{endpoint}.ipynb"

    def execute(self, endpoint):
        template_path = f"{self.template_dir}/{self.make_template_path(endpoint)}"
        outpath = self.make_outpath(endpoint)
        parameters = dict(path=f"{self.feedstock_id}.json")
        pm.execute_notebook(template_path, outpath, parameters=parameters)
