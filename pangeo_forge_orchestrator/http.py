from typing import Optional

import httpx


# Adapted https://github.com/tiangolo/fastapi/issues/236#issuecomment-716548461
# to use httpx instead of aiohttp. Mounts are optionally passable for mocking.
class HttpSession:
    session: httpx.AsyncClient = None

    def __init__(self, mounts: Optional[dict] = None) -> None:
        self.mounts = mounts

    def start(self):
        kw = dict(mounts=self.mounts) if self.mounts else {}
        self.session = httpx.AsyncClient(**kw)

    async def stop(self):
        await self.session.__aexit__()
        self.session = None

    def __call__(self) -> httpx.AsyncClient:
        assert self.session is not None
        return self.session


http_session = HttpSession()
