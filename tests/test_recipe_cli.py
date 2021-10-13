import pytest

from .check_stdout import check_stdout

subcommands = {
    "lint path-to-a-recipe": "Linting recipe path-to-a-recipe",
}
subcommands = [(cmd, output) for cmd, output in subcommands.items()]


@pytest.mark.parametrize("subcmd", subcommands)
def test_recipe_lint(subcmd):
    check_stdout(subcmd, module="recipe", drop_chars=("\n"))
