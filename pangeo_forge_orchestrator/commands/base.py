import logging

from traitlets import Unicode
from traitlets.config import Application

# Common aliases we want to support in *all* commands
# The key is what the commandline argument should be, and the
# value is the traitlet config it will be translated to
common_aliases = {
    "log-level": "Application.log_level",
    "f": "BaseCommand.config_file",
    "config": "BaseCommand.config_file",
}


class BaseCommand(Application):
    """
    Base Application for all our subcommands.
    Provides common traitlets everyone needs.
    Do not directly instantiate!
    """

    log_level = logging.INFO

    config_file = Unicode(
        "./config/local/deployment.py",
        config=True,
        help="""
        Load traitlets config from this file if it exists.
        Multiple config files can be passed at once (and typically are).
        """,
    )

    def initialize(self, argv=None):
        super().initialize(argv)
        # Load traitlets config from a config file if present
        self.load_config_file(self.config_file)
