import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

import aiohttp
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


def get_gcloud_auth_token():
    cmd = "gcloud auth print-identity-token".split()
    return subprocess.check_output(cmd).decode("utf-8").strip()


@dataclass
class GCPCloudRunSpawner(SpawnerABC):

    service_url: str
    token: str = field(default_factory=get_gcloud_auth_token)
    env: str = "notebook"

    async def check_output(self, cmd: List[str]):
        # FIXME: pkgs needs to be determined dynamically here based on fetching content
        # of requirements.txt from feedstock repo. this is a per-feedstock value, so cannot
        # be hardcoded as an instance attribute of this class.
        pkgs = ["pangeo-forge-runner==0.7.1"]
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.service_url,
                json={
                    "pangeo_forge_runner": {"cmd": cmd},
                    "install": {"pkgs": pkgs, "env": self.env},
                },
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
            ) as r:
                r_json = await r.json()
                if r.status == 202:
                    return r_json
                else:
                    # FIXME: spawner-specific error class.
                    # using this for now because github_app.py expects it.
                    raise subprocess.CalledProcessError(r.status, r_json)


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
