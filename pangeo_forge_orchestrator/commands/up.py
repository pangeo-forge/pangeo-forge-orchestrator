from ..configurables.fastapi import FastAPI
from .base import BaseCommand, common_aliases


class Up(BaseCommand):
    """Bring up Pangeo Forge Orchestrator services."""

    aliases = common_aliases

    def start(self):

        self.log.info("Going up!")

        fastapi = FastAPI(parent=self)
        fastapi.server.start()
