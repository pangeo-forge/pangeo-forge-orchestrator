import logging
import os
import subprocess
from pathlib import Path
from warnings import warn

from traitlets import List, Unicode
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

    config_file = List(
        Unicode(),
        ["./config/local/deployment.py"],
        config=True,
        help="""
        Load traitlets config from these files if they exist.
        Multiple config files can be passed at once (and typically are).
        """,
    )

    @property
    def secrets_dir_abspath(self):
        # FIXME: config_file should not be list?
        config_dir = os.path.split(self.config_file[0])[0]
        return Path(config_dir).resolve() / "secrets"

    def _encrypt_or_decrypt(self, method: str):
        """Encrypt or decrypt secrets.

        :param method: One of ``e`` (for encrypt) or ``d`` (for decrypt).
        """
        if self.secrets_dir_abspath.exists():
            self.log.info("Decrypting secrets...")
            for s in os.listdir(self.secrets_dir_abspath):
                cmd = f"sops -{method} -i {self.secrets_dir_abspath / s}".split()
                subprocess.run(cmd)
        else:
            warn("This deployment has no secrets dir.")

    def encrypt(self):
        self._encrypt_or_decrypt("e")

    def decrypt(self):
        self._encrypt_or_decrypt("d")

    def initialize(self, argv=None):
        super().initialize(argv)
        # Load traitlets config from a config file if present
        for f in self.config_file:
            self.log.info(f)
            self.load_config_file(f)
