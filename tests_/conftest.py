import os

mocking = True if not os.environ.get("TEST_REAL_3RD_PARTY_SERVICES") else False

if mocking:
    from conftest_mock import *  # noqa: F403
else:
    from conftest_real import *  # noqa: F403
