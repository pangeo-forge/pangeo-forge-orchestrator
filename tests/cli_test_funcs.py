import os
import subprocess


def check_output(subcmd, module, drop_chars):
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
    for char in drop_chars:
        out = out.replace(char, "")
    assert out == subcmd[1]
