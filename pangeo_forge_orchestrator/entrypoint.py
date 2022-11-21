from traitlets.config import Application

from .commands.down import Down
from .commands.up import Up


class App(Application):
    """Entrypoint for Pangeo Forge Orchestrator"""

    raise_config_file_errors = True

    subcommands = {
        "up": (Up, "Bring up orchestrator services."),
        "down": (Down, "Tear down all running orchestrator services."),
    }

    def start(self):
        self.parse_command_line()
        super().start()


def main():
    app = App()
    app.start()
