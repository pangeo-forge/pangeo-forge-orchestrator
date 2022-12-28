import subprocess
from abc import ABC, abstractmethod
from typing import List

from traitlets import Dict, Type
from traitlets.config import LoggingConfigurable


class RecipeCalledProcessResult:
    pass


class SpawnerABC(ABC):
    @abstractmethod
    def check_output(self, cmd: List[str]):
        """Spawn a new process, run a command in it, and return stdout.

        :param cmd: The command to run. Most commonly a call to `pangeo-forge-runner`.
        """
        pass


class LocalSubprocessSpawner(SpawnerABC):
    def check_output(self, cmd: List[str]):
        return subprocess.check_output(cmd)


class SpawnerConfig(LoggingConfigurable):
    """Spawner config."""

    cls = Type(
        klass=SpawnerABC,
        allow_none=False,
        config=True,
        help="""
        The spawner subclass to use for spawning recipe parsing processes.
        """,
    )

    kwargs = Dict(
        Dict(),
        allow_none=False,
        config=True,
        help="""
        Keyword arguments to be passed to ``self.cls``.
        """,
    )
