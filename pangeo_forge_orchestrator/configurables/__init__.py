import os

from traitlets import Type
from traitlets.config import Application, Configurable

from .deployment import Deployment  # noqa: F401
from .fastapi import FastAPI  # noqa: F401
from .github_app import GitHubApp  # noqa: F401
from .spawner import SpawnerABC, SpawnerConfig  # noqa: F401


class _GetConfigurable(Application):

    configurable = Type(
        klass=Configurable,
        allow_none=False,
    )

    def initialize(self, argv=None):
        super().initialize(argv)
        try:
            config_file = os.environ["ORCHESTRATOR_CONFIG_FILE"]
        except KeyError as e:  # pragma: no cover
            raise ValueError(
                "Application can't run unless ORCHESTRATOR_CONFIG_FILE "
                "environment variable is set"
            ) from e
        self.load_config_file(config_file)

    def resolve(self):
        if not self.initialized():
            self.initialize()
        return self.configurable(parent=self)


def get_configurable(configurable: Configurable) -> Configurable:
    """Convenience function to resolve global app config outside of ``traitlets`` object."""
    return _GetConfigurable(configurable=configurable).resolve()


def get_spawner() -> SpawnerABC:
    s: SpawnerConfig = _GetConfigurable(configurable=SpawnerConfig).resolve()
    return s.cls(**s.kwargs)
