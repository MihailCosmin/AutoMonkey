"""The committed MCP config must start the server on every OS."""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "automonkey", "ai", "mcp_launch.py")


def test_mcp_json_has_no_os_specific_paths():
    with open(os.path.join(ROOT, ".mcp.json")) as f:
        server = json.load(f)["mcpServers"]["automonkey"]
    spec = " ".join([server["command"]] + server.get("args", [])).replace("\\", "/")
    # a venv's interpreter lives in bin/ on Linux/macOS but Scripts/ on Windows
    assert "/bin/" not in spec and "Scripts/" not in spec and ".exe" not in spec, spec


def test_launcher_finds_the_venv_python(tmp_path):
    """--which must name the interpreter the server would actually run on.

    Skipped where there is nothing to find: no venv (CI installs the runtime requirements
    into its own interpreter, and the [ai] extra can't go on every matrix entry - mcp
    requires Python >= 3.10), and an interpreter that can't import the server's
    dependencies. What the launcher does in exactly that environment is the next test's job.
    """
    out = subprocess.run([sys.executable, LAUNCHER, "--which"], capture_output=True, text=True)
    if out.returncode != 0 and "no virtualenv found" in out.stderr:
        pytest.skip("no venv and no [ai] extra here: " + out.stderr.splitlines()[0])
    assert out.returncode == 0, out.stderr
    assert os.path.isfile(out.stdout.strip()), out.stdout


def test_launcher_explains_a_missing_venv(tmp_path):
    fake = tmp_path / "automonkey" / "ai"
    fake.mkdir(parents=True)
    shutil.copy(LAUNCHER, fake)
    env = {k: v for k, v in os.environ.items() if k not in ("AUTOMONKEY_VENV", "VIRTUAL_ENV")}
    # -I: don't let the real repo (cwd / PYTHONPATH) satisfy the import fallback
    r = subprocess.run([sys.executable, "-I", str(fake / "mcp_launch.py")], capture_output=True, text=True,
                       env=env, cwd=str(tmp_path))
    if r.returncode == 0:  # this interpreter has automonkey + mcp installed, so it is a valid fallback
        return
    assert r.returncode == 1 and "python -m venv .venv" in r.stderr
