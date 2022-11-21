from .base import BaseCommand


class Up(BaseCommand):
    def start(self):

        self.log.info("Going up!")
