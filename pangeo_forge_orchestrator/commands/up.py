from ..configurables.github_app import GitHubApp
from .base import BaseCommand, common_aliases


class Up(BaseCommand):
    """Bring up Pangeo Forge Orchestrator services."""

    aliases = common_aliases

    def start(self):

        self.log.info("Going up!")

        github_app = GitHubApp(parent=self)
        self.log.info(github_app)
        self.log.info(github_app.app_name)
        self.log.info(github_app.id)
        self.log.info(github_app.private_key)
        self.log.info(github_app.webhook_secret)
