"""Start the MCP server with the project's virtualenv, on any OS.

A venv keeps its interpreter in `.venv/bin/python` on Linux/macOS but in
`.venv\\Scripts\\python.exe` on Windows, and `.mcp.json` can't branch on the OS. So
`.mcp.json` runs this file with whatever Python is at hand (stdlib only, any 3.x);
it finds the venv's interpreter and hands over to the real server.

    python3 automonkey/ai/mcp_launch.py           # start the server
    python3 automonkey/ai/mcp_launch.py --which   # print the interpreter it would use

Looks in $AUTOMONKEY_VENV, then <repo>/.venv, <repo>/venv, then $VIRTUAL_ENV; falls
back to the running interpreter if it can import the server.
"""
import importlib.util
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def venv_python():
    for venv in (os.environ.get("AUTOMONKEY_VENV"), os.path.join(ROOT, ".venv"), os.path.join(ROOT, "venv"),
                 os.environ.get("VIRTUAL_ENV")):
        if not venv:
            continue
        for exe in (os.path.join(venv, "Scripts", "python.exe"), os.path.join(venv, "bin", "python")):
            if os.path.isfile(exe):
                return exe
    # The server runs with cwd=ROOT, so the package comes from there; only its dependencies
    # have to be installed in this interpreter.
    server = os.path.join(ROOT, "automonkey", "ai", "mcp_server.py")
    if os.path.isfile(server) and all(importlib.util.find_spec(m) for m in ("mcp", "pyautogui")):
        return sys.executable
    return None


def main():
    python = venv_python()
    if not python:
        pip = r".venv\Scripts\pip" if sys.platform == "win32" else ".venv/bin/pip"
        sys.stderr.write("automonkey MCP: no virtualenv found in {}. Create it:\n"
                         "  python -m venv .venv && {} install -e .[ai]\n"
                         "or point AUTOMONKEY_VENV at an existing one.\n".format(ROOT, pip))
        return 1
    if "--which" in sys.argv:
        print(python)
        return 0
    cmd = [python, "-m", "automonkey.ai.mcp_server"]
    if sys.platform != "win32":
        os.chdir(ROOT)
        os.execv(python, cmd)  # replace this process: signals and stdio go straight to the server
    # Windows has no real exec (os.execv spawns and exits, detaching stdio), so run it as a
    # child that inherits our stdin/stdout pipes, and pass its exit code on.
    try:
        return subprocess.call(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
