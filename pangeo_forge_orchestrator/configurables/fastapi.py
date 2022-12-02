from traitlets import Unicode, validate
from traitlets.config import LoggingConfigurable

from .types import SecretStr


class FastAPI(LoggingConfigurable):
    """Config for the FastAPI instance."""

    key = Unicode(
        allow_none=False,
        config=True,
        help="""

        """,
    )

    @validate("key")
    def _cast_secrets(self, proposal):
        """Cast secret values to ``SecretStr``s."""
        return SecretStr(proposal["value"])
