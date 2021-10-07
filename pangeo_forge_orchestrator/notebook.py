import tempfile
from dataclasses import dataclass, field

import papermill as pm


class Notebook

    bakery_database: str = 

    def execute_notebook(template_path, parameters):
        outpath = tempfile.NamedTemporaryFile()
        pm.execute_notebook(template_path, outpath.name, parameters=parameters)
        return outpath.name
