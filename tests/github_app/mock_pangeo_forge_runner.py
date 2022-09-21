from typing import List


def mock_subprocess_check_output(cmd: List[str]):
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
        else:
            raise NotImplementedError(f"Command {cmd} not implemented in tests.")
    else:
        raise NotImplementedError(
            f"Command {cmd} does not begin with 'pangeo-forge-runner'. Currently, "
            "'pangeo-forge-runner' is the only command line mock implemented."
        )
