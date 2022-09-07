import subprocess


def test_runner_callable():
    cmd = ["pangeo-forge-runner", "--help"]
    subprocess.check_call(cmd)
