import pytest

from .cli_test_funcs import check_output

subcommands = {
    "lint path-to-a-recipe": "Linting recipe path-to-a-recipe",
}
subcommands = [(cmd, output) for cmd, output in subcommands.items()]


@pytest.mark.parametrize("subcmd", subcommands)
def test_recipe_lint(subcmd):
    check_output(subcmd, module="recipe", drop_chars=("\n"))
