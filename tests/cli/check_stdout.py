import ast
import os
import subprocess


def drop_characters(outstring, drop_chars):
    for char in drop_chars:
        outstring = outstring.replace(char, "")
    return outstring


def check_stdout(subcmd, module, drop_chars, eval_dict=False):
    """
    subcmd: 2-tuple
        Pair of subcommand + expected output.
    module: submodule
        Submodule within `pangeo-forge` cli.
    drop_chars: tuple
        Characters to drop from returned output.
    """
    cmd = ["pangeo-forge", module]
    for arg in subcmd[0].split(" "):
        cmd.append(arg)
    env = dict(os.environ, COLUMNS="200")
    out = subprocess.check_output(cmd, env=env)
    out = out.decode("utf-8")
    out = drop_characters(out, drop_chars=drop_chars)
    if eval_dict:
        d0 = ast.literal_eval(out)
        d1 = ast.literal_eval(subcmd[1])
        assert d0 == d1
    else:
        expected_resp = drop_characters(subcmd[1], drop_chars=drop_chars)
        assert out == expected_resp
