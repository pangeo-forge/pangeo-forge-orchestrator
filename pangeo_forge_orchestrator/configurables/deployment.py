import os

from traitlets import Dict, List, Type, Unicode, default, validate
from traitlets.config import LoggingConfigurable

from ..spawners.base import BaseSpawner
from ..spawners.local_subprocess import LocalSubprocessSpawner
from .types import SecretList, SecretStr


class Deployment(LoggingConfigurable):
    """Global config for the deployment instance."""

    name = Unicode(
        allow_none=False,
        config=True,
        help="""
        The name of the deployment.
        """,
    )

    database_url = Unicode(
        allow_none=False,
        config=True,
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

    dont_leak = List(
        allow_none=False,
        config=True,
        help="""
        A list of secret values which the application needs to run, but which
        we want to avoid accidentally leaking to logs or in print statements.
        """,
    )

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
        Dict(),
        allow_none=False,
        config=True,
        help="""
        A dictionary of runner configs to support at runtime.
        Users on GitHub specify which runner config to deploy their job with in the
        meta.yaml file provided in their feedstock (or PR).
        The specified runner config (i.e. "bakery id") must be a key in this dict.
        """,
    )
    # see note about naming clarity above
    bakeries = registered_runner_configs

    @default("database_url")
    def _database_url_from_env(self):
        try:
            database_url = os.environ["DATABASE_URL"]
        except KeyError as e:  # pragma: no cover
            raise ValueError(
                "Application can't run unless DATABASE_URL environment variable is set"
            ) from e

        if database_url.startswith("postgres://"):  # pragma: no cover
            # Fix Heroku's incompatible postgres database uri
            # https://stackoverflow.com/a/67754795/3266235
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    @validate("dont_leak")
    def _valid_dont_leak(self, proposal):
        """Cast the list of strings passed to ``self.dont_leak`` to a ``SecretList`` of
        ``SecretStr``s, to minimize the possibility that they will be accidentally leaked
        in logs or by print statements.
        """
        return SecretList([SecretStr(v) for v in proposal["value"]])

    def hide_secrets(self, d: dict) -> dict:
        """If the input dict contains any values which are members of ``self.dont_leak``,
        hide them as ``SecretStr``s. This prevents these values from being accidentally
        logged or printed, but they can still be accessed via ``json.dump`` as shown here:

            >>> import json

            >>> d = {"a": 1, "b": {"c": "secret"}}
            >>> protected = hide_secrets(["secret"], d)
            >>> print(protected)
            {'a': 1, 'b': {'c': *****}}
            >>> json.dumps(protected)
            '{"a": 1, "b": {"c": "secret"}}'
        """
        return {
            k: (v if v not in self.dont_leak else SecretStr(v))
            if not isinstance(v, dict)
            else self.hide_secrets(v)
            for k, v in d.items()
        }

    # For cross-validation approach used in the following methods, see:
    # https://traitlets.readthedocs.io/en/stable/using_traitlets.html#custom-cross-validation

    @validate("registered_runner_configs")
    def _valid_registered_runner_configs(self, proposal):
        """For all registered runner configs, cast any secret values to ``SecretStr``s."""
        return self.hide_secrets(proposal["value"])
