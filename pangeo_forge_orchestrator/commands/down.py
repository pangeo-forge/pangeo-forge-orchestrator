from .base import BaseCommand


class Down(BaseCommand):
    def start(self):

        self.log.info("Coming down!")
