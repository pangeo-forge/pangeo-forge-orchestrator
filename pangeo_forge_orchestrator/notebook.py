# import tempfile
# from dataclasses import dataclass

import papermill as pm

# @dataclass
# class ExecuteNotebook


def execute(template_path, outfile, parameters):
    # outfile = tempfile.NamedTemporaryFile(suffix=".ipynb")
    pm.execute_notebook(template_path, outfile, parameters=parameters)
    # return outfile.name
