from traitlets import Dict, Type, Unicode
from traitlets.config import LoggingConfigurable

from ..spawners.base import BaseSpawner
from ..spawners.local_subprocess import LocalSubprocessSpawner


class Deployment(LoggingConfigurable):

    name = Unicode(
        allow_none=False,
        config=True,
        help="""
        The name of the deployment.
        """,
    )

    spawner = Type(
        default_value=LocalSubprocessSpawner,
        klass=BaseSpawner,
        allow_none=False,
        config=True,
        help="""
        The spawner subclass to use for spawning recipe parsing processes.
        """,
    )

    fastapi = Dict()

    github_app = Dict()

    # TODO: Naming clarity can be improved here. This traitlet uses the name `runner config`,
    # because that's what it actually is: config for `pangeo-forge-runner`. From a user
    # perspective, though, the keys of this dict are specified as the `bakery id` in meta.yaml.
    # I am leaving this tension intact for now (rather than trying to resolve it here), because
    # it touches at least two other unresolved issues: renaming of `pangeo-forge-runner`
    # (see: https://github.com/pangeo-forge/pangeo-forge-runner/issues/24); and also the fact that
    # a first draft version-controlled schema for meta.yaml has not yet been created. Of course,
    # the naming confusion with Beam Runners also complicates this, but that point is covered in
    # the linked `pangeo-forge-runner` issue.
    registered_runner_configs = Dict(
        Dict,
        allow_none=False,
        config=True,
        help="""
        A dictionary of runner configs to support at runtime.
        Users on GitHub specify which runner config to deploy their job with in the
        meta.yaml file provided in their feedstock (or PR).
        The specified runner config (i.e. "bakery id") must be a key in this dict.
        """,
    )
