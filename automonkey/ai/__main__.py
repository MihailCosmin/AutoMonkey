"""Command line for agents that only have a shell (one command = act + screenshot).

    python -m automonkey.ai shot [--grid 100]
    python -m automonkey.ai do "launch firefox; maximize; url google.ro"
    python -m automonkey.ai zoom X Y W H
    python -m automonkey.ai windows
    python -m automonkey.ai find "Accept all"
    python -m automonkey.ai read [X Y W H]
    python -m automonkey.ai controls "Notepad" [--all] [--depth N]
    python -m automonkey.ai history [N]
    python -m automonkey.ai replay tests/ui/*.amk      (exit code 1 if any script fails)

Screenshots are written to --out (default: $AUTOMONKEY_AI_OUT or
/tmp/automonkey_ai/screen.png) and the path is printed; open it to look.
Coordinates are pixels of that screenshot.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

from . import act, history, observe, ocr, replay, screen, window_list

DEFAULT_OUT = os.environ.get("AUTOMONKEY_AI_OUT",
                             os.path.join(tempfile.gettempdir(), "automonkey_ai", "screen.png"))


def _save(img, out: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, compress_level=1)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m automonkey.ai", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=DEFAULT_OUT, help="where to save the screenshot")
    p.add_argument("--grid", type=int, default=0, help="overlay a labelled grid every N pixels")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("shot", help="take a screenshot")
    d = sub.add_parser("do", help="run an action script, then take a screenshot")
    d.add_argument("script", help="steps separated by ';' or newlines ('-' reads stdin)")
    d.add_argument("--no-shot", action="store_true", help="don't take a screenshot")
    z = sub.add_parser("zoom", help="enlarged view of a region")
    z.add_argument("box", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    sub.add_parser("windows", help="list windows")
    f = sub.add_parser("find", help="find text on screen (OCR)")
    f.add_argument("text")
    r = sub.add_parser("read", help="read text on screen (OCR)")
    r.add_argument("box", type=int, nargs="*", metavar="X Y W H")
    c = sub.add_parser("controls", help="list a window's controls with click points (Windows)")
    c.add_argument("window")
    c.add_argument("--all", action="store_true", help="include non-interactive elements")
    c.add_argument("--depth", type=int, default=None)
    h = sub.add_parser("history", help="scripts run today, as .amk text")
    h.add_argument("n", type=int, nargs="?", default=20)
    rp = sub.add_parser("replay", help="run saved .amk regression scripts")
    rp.add_argument("files", nargs="+")
    ic = sub.add_parser("install-claude", help="install the visual-testing skill and register this MCP server "
                                               "for Claude Code in every project (user scope)")
    ic.add_argument("--config-dir", default=os.environ.get("CLAUDE_CONFIG_DIR")
                    or os.path.join(os.path.expanduser("~"), ".claude"),
                    help="Claude Code config folder (default: $CLAUDE_CONFIG_DIR or ~/.claude)")
    ic.add_argument("--no-mcp", action="store_true", help="only install the skill")
    a = p.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # control names and OCR text are Unicode
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if a.cmd == "shot":
        text, img = observe(grid=a.grid)
        print(text)
        print("screenshot:", _save(img, a.out))
    elif a.cmd == "do":
        script = sys.stdin.read() if a.script == "-" else a.script
        text, img = act(script, screenshot=not a.no_shot, grid=a.grid)
        print(text)
        if img is not None:
            print("screenshot:", _save(img, a.out))
        return 0 if not text.startswith("STOPPED") else 1
    elif a.cmd == "zoom":
        print("zoom:", _save(screen.zoom(*a.box, grid=a.grid), a.out.replace(".png", "_zoom.png")))
    elif a.cmd == "windows":
        print(window_list())
    elif a.cmd == "find":
        hits = ocr.find_text(a.text)
        print("\n".join(f"{h['text']!r} click at {h['cx']},{h['cy']}" for h in hits) or "not found")
    elif a.cmd == "read":
        print(ocr.read_text(*(a.box or [0, 0, 0, 0])))
    elif a.cmd == "controls":
        from . import controls
        print(controls.tree(a.window, depth=a.depth, interactive_only=not a.all))
    elif a.cmd == "history":
        print(history(a.n))
    elif a.cmd == "replay":
        failed = 0
        for path in a.files:
            ok, log, _img = replay(path)
            print(log)
            failed += not ok
        print(f"{len(a.files) - failed} passed, {failed} failed")
        return 1 if failed else 0
    elif a.cmd == "install-claude":
        return _install_claude(a.config_dir, mcp=not a.no_mcp)
    return 0


def _install_claude(config_dir: str, mcp: bool = True) -> int:
    """Copy skills/visual-testing into <config>/skills and register the MCP server with
    `claude mcp add --scope user`, pointing at this interpreter (the venv) so it works
    from any project directory."""
    import shutil
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = os.path.join(root, "skills", "visual-testing")
    if not os.path.isdir(src):
        print(f"no skills/visual-testing next to the package ({root}): run this from a source checkout")
        return 1
    dst = os.path.join(config_dir, "skills", "visual-testing")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)
    print(f"skill installed: {dst}")
    if not mcp:
        return 0
    claude = shutil.which("claude")
    launcher = os.path.join(root, "automonkey", "ai", "mcp_launch.py")
    add = ["mcp", "add", "--scope", "user", "automonkey", "--", sys.executable, launcher]
    if not claude:
        print("claude CLI not found; register the MCP server yourself:\n  claude " + " ".join(f'"{x}"' for x in add))
        return 0
    subprocess.run([claude, "mcp", "remove", "--scope", "user", "automonkey"], capture_output=True)
    done = subprocess.run([claude, *add], capture_output=True, text=True)
    print((done.stdout + done.stderr).strip() or "MCP server registered")
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
