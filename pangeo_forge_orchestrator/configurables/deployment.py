from traitlets import Unicode
from traitlets.config import LoggingConfigurable


class Deployment(LoggingConfigurable):

    name = Unicode(
        allow_none=False,
        config=True,
        help="""
        The name of the deployment.
        """,
    )
