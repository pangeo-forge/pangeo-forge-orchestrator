from traitlets import Int, Unicode
from traitlets.config import LoggingConfigurable


class GitHubApp(LoggingConfigurable):
    """Config for the GitHub App instance which serves as
    the GitHub integration point for the FastAPI instance.
    """

    app_name = Unicode(
        allow_none=False,
        config=True,
        help="""

        """,
    )

    id = Int(
        allow_none=False,
        config=True,
        help="""

        """,
    )

    private_key = Unicode(
        allow_none=False,
        config=True,
        help="""

        """,
    )

    webhook_secret = Unicode(
        allow_none=False,
        config=True,
        help="""

        """,
    )
