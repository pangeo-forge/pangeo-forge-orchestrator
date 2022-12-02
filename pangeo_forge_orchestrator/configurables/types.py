class SecretStr(str):
    """A string, except it's hard to accidentally print or log it."""

    def __str__(self) -> str:
        return "*****"

    def __repr__(self) -> str:
        return "*****"


class SecretList(list):
    """A list, except it's hard to accidentally print or log it."""

    def __str__(self) -> str:
        return "[***, ***, ***]"

    def __repr__(self) -> str:
        return "[***, ***, ***]"
