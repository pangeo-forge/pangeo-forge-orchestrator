import aiohttp


# See https://github.com/tiangolo/fastapi/issues/236#issuecomment-716548461
class HttpSession:
    session: aiohttp.ClientSession = None

    def start(self):
        self.session = aiohttp.ClientSession()

    async def stop(self):
        await self.session.close()
        self.session = None

    def __call__(self) -> aiohttp.ClientSession:
        assert self.session is not None
        return self.session


http_session = HttpSession()
