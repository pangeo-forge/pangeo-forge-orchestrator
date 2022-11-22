from ..configurables.deployment import Deployment
from .base import BaseCommand, common_aliases


class Up(BaseCommand):
    """Bring up Pangeo Forge Orchestrator services."""

    aliases = common_aliases

    def start(self):

        self.log.info("Going up!")

        deployment = Deployment(parent=self)
        self.log.info(deployment.name)
