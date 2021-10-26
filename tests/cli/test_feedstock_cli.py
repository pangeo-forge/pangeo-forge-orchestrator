import pytest

from .check_stdout import check_stdout

subcommands = {
    "--help": (
        "Usage: pangeo-forge feedstock [OPTIONS] COMMAND [ARGS]..."
        "Options:  --help  Show this message and exit."
    )
}
subcommands = [(cmd, output) for cmd, output in subcommands.items()]


@pytest.mark.parametrize("subcmd", subcommands)
def test_recipe_lint(subcmd):
    check_stdout(subcmd, module="feedstock", drop_chars=("\n"))
