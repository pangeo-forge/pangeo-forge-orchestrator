import pytest

from .check_stdout import check_stdout

cmds_and_responses = [["lint path/to-a/recipe", "Linting recipe path/to-a/recipe"]]


@pytest.mark.parametrize("subcmd", cmds_and_responses)
def test_recipe_lint(subcmd):
    check_stdout(subcmd, module="recipe", drop_chars=("\n"))
