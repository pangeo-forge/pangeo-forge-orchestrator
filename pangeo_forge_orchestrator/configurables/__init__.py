from traitlets import Type
from traitlets.config import Configurable

from ..commands.base import BaseCommand
from .deployment import Deployment  # noqa: F401
from .fastapi import FastAPI  # noqa: F401
from .github_app import GitHubApp  # noqa: F401


class _GetConfigurable(BaseCommand):

    configurable = Type(
        klass=Configurable,
        allow_none=False,
    )

    def resolve(self):
        # if not self.initialized():
        self.initialize()
        return self.configurable(parent=self)


def get_configurable(configurable: Configurable) -> Configurable:
    """Convenience function to resolve global app config outside of ``traitlets`` object."""
    return _GetConfigurable(configurable=configurable).resolve()
