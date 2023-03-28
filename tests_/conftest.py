import os

mocking = True if not os.environ.get("TEST_REAL_3RD_PARTY_SERVICES") else False

if mocking:
    from .fixtures_mock.general import *  # noqa: F403
    from .fixtures_mock.pull_request_synchronize import *  # noqa: F403
else:
    ...
