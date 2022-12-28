import subprocess
from typing import List

from .base import Spawner


class LocalSubprocessSpawner(Spawner):
    def check_output(self, cmd: List[str]):
        return subprocess.check_output(cmd)
