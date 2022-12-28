from abc import ABC, abstractmethod
from typing import List


class RecipeCalledProcessResult:
    pass


class Spawner(ABC):
    @abstractmethod
    def check_output(self, cmd: List[str]):
        """Spawn a new process, run a command in it, and return stdout.

        :param cmd: The command to run. Most commonly a call to `pangeo-forge-runner`.
        """
        pass
