import json
from subprocess import CalledProcessError


def mock_subprocess_check_output_raises_called_process_error(cmd: list[str]):
    subcmd = cmd[1]
    if subcmd == "bake":
        loglines = [
            # fmt: off
            {"message": "Target Storage is FSSpecTarget(AbstractFileSystem(, root_path=\"\")\n", "status": "setup"},
            {"message": "Input Cache Storage is CacheFSSpecTarget(AbstractFileSystem(, root_path=\"\")\n", "status": "setup"},
            {"message": "Metadata Cache Storage is MetadataTarget(AbstractFileSystem(, root_path=\"\")\n", "status": "setup"},
            {"message": "Picked Git content provider.\n", "status": "fetching"},
            {"message": "Cloning into '/var/folders/tt/4f941hdn0zq549zdwhcgg98c0000gn/T/tmp6mcx0gyk'...\n", "status": "fetching"},
            {"message": "HEAD is now at 0375426 Removed references to setup_logging\n", "status": "fetching"},
            {"message": "Parsing recipes...", "status": "running"},
            {"message": "Baking only recipe_id='eooffshore_ics_cmems_WIND_GLO_WIND_L3_NRT_OBSERVATIONS_012_002_MetOp_ASCAT'"},
            {"message": "Error during running: object of type function not serializable", "exc_info": "Traceback (most recent call last):\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/bin/pangeo-forge-runner\", line 8, in <module>\n    sys.exit(main())\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/pangeo_forge_runner/cli.py\", line 28, in main\n    app.start()\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/pangeo_forge_runner/cli.py\", line 23, in start\n    super().start()\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/traitlets/config/application.py\", line 462, in start\n    return self.subapp.start()\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/pangeo_forge_runner/commands/bake.py\", line 130, in start\n    job_name = f\"{name}-{recipe.sha256().hex()}-{int(datetime.now().timestamp())}\"\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/pangeo_forge_recipes/recipes/base.py\", line 51, in sha256\n    return dataclass_sha256(self, ignore_keys=self._hash_exclude_)\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/pangeo_forge_recipes/serialization.py\", line 70, in dataclass_sha256\n    return dict_to_sha256(d)\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/pangeo_forge_recipes/serialization.py\", line 31, in dict_to_sha256\n    b = dumps(\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/json/__init__.py\", line 234, in dumps\n    return cls(\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/json/encoder.py\", line 199, in encode\n    chunks = self.iterencode(o, _one_shot=True)\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/json/encoder.py\", line 257, in iterencode\n    return _iterencode(o, 0)\n  File \"/Users/charlesstern/miniconda3/envs/pfo-new/lib/python3.9/site-packages/pangeo_forge_recipes/serialization.py\", line 20, in either_encode_or_hash\n    raise TypeError(f\"object of type {type(obj).__name__} not serializable\")\nTypeError: object of type function not serializable", "status": "failed"},
            # fmt: on
        ]
    output = "\n".join([json.dumps(line) for line in loglines])
    raise CalledProcessError(1, cmd, output)


def mock_subprocess_check_output(cmd: list[str]):
    """ """

    if cmd[0] == "pangeo-forge-runner":
        if cmd[1] == "expand-meta":
            # As a first step, we are not accounting for any arguments passed to expand-meta.
            # This return value was obtained by running, with pangeo-forge-runner==0.3
            #  ```
            #  subprocess.check_output(
            #      "pangeo-forge-runner expand-meta --repo https://github.com/pangeo-forge/github-app-sandbox-repository --ref 0fd9b13f0d718772e78fc2b53fd7e9da82a522f3 --json".split()
            #  )
            #  ```
            return (
                '{"message": "Picked Git content provider.\\n", "status": "fetching"}\n'
                '{"message": "Cloning into \'/var/folders/tt/4f941hdn0zq549zdwhcgg98c0000gn/T/tmp10gezh_p\'...\\n", "status": "fetching"}\n'
                '{"message": "HEAD is now at 0fd9b13 Update foo.txt\\n", "status": "fetching"}\n'
                '{"message": "Expansion complete", "status": "completed", "meta": {"title": "Global Precipitation Climatology Project", "description": "Global Precipitation Climatology Project (GPCP) Daily Version 1.3 gridded, merged ty satellite/gauge precipitation Climate data Record (CDR) from 1996 to present.\\n", "pangeo_forge_version": "0.9.0", "pangeo_notebook_version": "2022.06.02", "recipes": [{"id": "gpcp", "object": "recipe:recipe"}], "provenance": {"providers": [{"name": "NOAA NCEI", "description": "National Oceanographic & Atmospheric Administration National Centers for Environmental Information", "roles": ["host", "licensor"], "url": "https://www.ncei.noaa.gov/products/global-precipitation-climatology-project"}, {"name": "University of Maryland", "description": "University of Maryland College Park Earth System Science Interdisciplinary Center (ESSIC) and Cooperative Institute for Climate and Satellites (CICS).\\n", "roles": ["producer"], "url": "http://gpcp.umd.edu/"}], "license": "No constraints on data access or use."}, "maintainers": [{"name": "Ryan Abernathey", "orcid": "0000-0001-5999-4917", "github": "rabernat"}], "bakery": {"id": "pangeo-ldeo-nsf-earthcube"}}}\n'
            )
        elif cmd[1] == "bake":
            return b'{"message": "Submitted job 2022-11-02_09_47_12-7631717319482580875 for recipe NASA-SMAP-SSS/RSS/monthly","recipe": "NASA-SMAP-SSS/RSS/monthly","job_name": "a6170692e70616e67656f2d666f7267652e6f7267251366","job_id": "2022-11-02_09_47_12-7631717319482580875","status": "submitted"}'
        else:
            raise NotImplementedError(f"Command {cmd} not implemented in tests.")
    else:
        raise NotImplementedError(
            f"Command {cmd} does not begin with 'pangeo-forge-runner'. Currently, "
            "'pangeo-forge-runner' is the only command line mock implemented."
        )
