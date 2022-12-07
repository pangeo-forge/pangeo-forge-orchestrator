# from ..configurables.deployment import Deployment
from .base import BaseCommand, common_aliases


class Release(BaseCommand):
    """Release Pangeo Forge Orchestrator services."""

    aliases = common_aliases

    def start(self):

        self.log.info(f"Releasing services defined in {self.config_file}")

        # deployment = Deployment(parent=self)
