from traitlets import Int, Unicode, validate
from traitlets.config import LoggingConfigurable

from ._types import SecretStr


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

    @validate("private_key", "webhook_secret")
    def _cast_secrets(self, proposal):
        """Cast secret values to ``SecretStr``s."""
        return SecretStr(proposal["value"])
