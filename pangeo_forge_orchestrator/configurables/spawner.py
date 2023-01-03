import asyncio
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

import aiohttp
import traitlets
from traitlets.config import LoggingConfigurable


class RecipeCalledProcessResult:
    pass


class RecipeCalledProcessError(subprocess.CalledProcessError):
    pass


def get_subprocess_executable():
    # putting this in a function facilitates mocking in tests
    return "pangeo-forge-runner"


class SpawnerABC(ABC):
    @abstractmethod
    def check_output(self, cmd: List[str]):
        """Spawn a new process, run a command in it, and return stdout.

        :param cmd: The command to run. Most commonly a call to `pangeo-forge-runner`.
        """
        pass


class LocalSubprocessSpawner(SpawnerABC):
    async def check_output(self, cmd: List[str]):
        # https://docs.python.org/3/library/asyncio-subprocess.html#asyncio-subprocess
        proc = await asyncio.create_subprocess_shell(
            get_subprocess_executable() + " " + " ".join(cmd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return stdout.decode()
        else:
            returncode = proc.returncode if proc.returncode else 1
            raise RecipeCalledProcessError(returncode, cmd, output=stderr.decode())


def get_gcloud_auth_token():
    cmd = "gcloud auth print-identity-token".split()
    # TODO: use asyncio subprocess
    return subprocess.check_output(cmd).decode("utf-8").strip()


@dataclass
class GCPCloudRunSpawner(SpawnerABC):

    service_url: str
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
                    # calling gcloud for the token on each request has a performance cost, but this
                    # way we avoid ever holding the token in an instance attribute, which would
                    # increase the risk of it accidentally leaking to logs, etc.
                    "Authorization": f"Bearer {get_gcloud_auth_token()}",
                    "Content-Type": "application/json",
                },
            ) as r:
                r_json = await r.json()
                if r.status == 202:
                    return r_json["pangeo_forge_runner_result"]
                else:
                    raise RecipeCalledProcessError(r.status, cmd, output=r_json)


class SpawnerConfig(LoggingConfigurable):
    """Spawner config."""

    cls = traitlets.Type(
        klass=SpawnerABC,
        allow_none=False,
        config=True,
        help="""
        The spawner subclass to use for spawning recipe parsing processes.
        """,
    )

    kws = traitlets.Dict(
        allow_none=False,
        config=True,
        help="""
        Keyword arguments to be passed to ``self.cls``.
        """,
    )
