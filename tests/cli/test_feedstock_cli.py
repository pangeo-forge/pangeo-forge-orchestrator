import pytest

from .check_stdout import check_stdout

cmds_and_responses = [
    [
        "--help",
        """Usage: pangeo-forge feedstock [OPTIONS] COMMAND [ARGS]...

        Options:
        --help  Show this message and exit.
        """,
    ]
]


@pytest.mark.parametrize("cmd_and_resp", cmds_and_responses)
def test_recipe_lint(cmd_and_resp):
    check_stdout(cmd_and_resp, module="feedstock", drop_chars=(" ", "\n"))
