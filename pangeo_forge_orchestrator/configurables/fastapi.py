from traitlets import Unicode
from traitlets.config import LoggingConfigurable


class FastAPI(LoggingConfigurable):
    """Config for the FastAPI instance."""

    key = Unicode(
        allow_none=False,
        config=True,
        help="""

        """,
    )
