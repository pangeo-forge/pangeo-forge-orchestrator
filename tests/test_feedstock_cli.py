import pytest

from .cli_test_funcs import check_output

subcommands = {
    "--help": (
        "Usage: pangeo-forge feedstock [OPTIONS] COMMAND [ARGS]..."
        "Options:  --help  Show this message and exit."
    )
}
subcommands = [(cmd, output) for cmd, output in subcommands.items()]


@pytest.mark.parametrize("subcmd", subcommands)
def test_recipe_lint(subcmd):
    check_output(subcmd, module="feedstock", drop_chars=("\n"))
