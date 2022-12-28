import subprocess
from pathlib import Path

from traitlets import Int, TraitType, Unicode, validate
from traitlets.config import LoggingConfigurable

from ._types import SecretStr

root_dir = Path(__file__).parent.parent.parent.resolve()


class Server:
    def start(self):
        pass


class UvicornServer(Server):
    def start(self):
        cmd = (
            "uvicorn pangeo_forge_orchestrator.api:app "
            f"--reload --reload-dir={root_dir}/pangeo_forge_orchestrator"
        ).split()
        subprocess.run(cmd)


class GunicornServer(LoggingConfigurable):

    nworkers = Int(
        2,
    )

    timeout = Int(
        300,
    )

    def start(self):
        cmd = (
            "gunicorn "
            f"-w {self.nworkers} "
            f"-t {self.timeout} "
            "-k uvicorn.workers.UvicornWorker "
            "pangeo_forge_orchestrator.api:app"
        ).split()
        subprocess.run(cmd)


class FastAPI(LoggingConfigurable):
    """Config for the FastAPI instance."""

    key = Unicode(
        allow_none=False,
        config=True,
        help="""

        """,
    )

    server: Server = TraitType(
        UvicornServer(),
        klass=Server,
        allow_none=False,
        config=True,
        help="""

        """,
    )

    @validate("key")
    def _cast_secrets(self, proposal):
        """Cast secret values to ``SecretStr``s."""
        return SecretStr(proposal["value"])
