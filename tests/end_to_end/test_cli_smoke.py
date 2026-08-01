import subprocess
import sys


def test_cli_version_cmd():
    cmd = [sys.executable, "-m", "rekanvault.cli", "version"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "v0.1.0" in res.stdout


def test_cli_health_cmd():
    cmd = [sys.executable, "-m", "rekanvault.cli", "health"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert '"status": "ok"' in res.stdout
