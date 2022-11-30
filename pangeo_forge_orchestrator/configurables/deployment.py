from traitlets import Dict, List, Type, Unicode, validate
from traitlets.config import LoggingConfigurable

from ..commands.base import BaseCommand
from ..spawners.base import BaseSpawner
from ..spawners.local_subprocess import LocalSubprocessSpawner


class SecretStr(str):
    """A string, except it's hard to accidentally print or log it."""

    def __str__(self) -> str:
        return "*****"

    def __repr__(self) -> str:
        return "*****"


class SecretList(list):
    """A list, except it's hard to accidentally print or log it."""

    def __str__(self) -> str:
        return "[***, ***, ***]"

    def __repr__(self) -> str:
        return "[***, ***, ***]"


class DotAccessibleDict(dict):
    """A dict, but all keys are also accessible as dotted attributes."""

    # This is a (possibly temporary) patch/hack to accomodate the fact that, pre-traitlets, config
    # is commonly dot-accessed. In migrating to traitlets, I want to touch as little of the existing
    # code as possible for now. To do this, we need nested config objects in Deployment to support
    # __getattr__. Other than this, though, a dict is fine, so I've just wired __getattr__ to
    # __getitem__ for now. I previously tried to make these objects subclasses of traitlets.HasTraits,
    # but couldn't make that work when setting them as traits of the configurable Deployment, below.
    def __getattr__(self, attr):
        return self.get(attr)


class FastAPIConfig(DotAccessibleDict):
    pass


class GitHubAppConfig(DotAccessibleDict):
    pass


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

    dont_leak = List(
        allow_none=False,
        config=True,
        help="""
        A list of secret values which the application needs to run, but which
        we want to avoid accidentally leaking to logs or in print statements.
        """,
    )

    fastapi = Dict(
        allow_none=False,
        config=True,
    )

    github_app = Dict(
        allow_none=False,
        config=True,
        help="""
        Config for the GitHub App instance which serves as
        the GitHub integration point for this application.
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

    @validate("github_app")
    def _valid_github_app(self, proposal):
        """Cast input dict to ``GitHubAppConfig`` (and secret vals to ``SecretStr``s)."""
        return GitHubAppConfig(**self.hide_secrets(proposal["value"]))

    @validate("fastapi")
    def _valid_fastapi(self, proposal):
        """Cast input dict to ``FastAPIConfig`` (and secret vals to ``SecretStr``s)."""
        return FastAPIConfig(**self.hide_secrets(proposal["value"]))


class _GetDeployment(BaseCommand):
    def resolve(self):
        # if not self.initialized():
        self.initialize()
        return Deployment(parent=self)


def get_deployment() -> Deployment:
    """Convenience function to resolve global app config outside of ``traitlets`` object."""
    return _GetDeployment().resolve()
