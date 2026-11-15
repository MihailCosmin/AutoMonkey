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
    python -m automonkey.ai replay a.amk --var OUT=docs/shots --json report.json --no-failure-shot
    python -m automonkey.ai capture shot.png --window "My App" [--pad 8]      (native-resolution PNG)
    python -m automonkey.ai capture shot.png --region X Y W H                 (screen pixels)
    python -m automonkey.ai bounds shot.json --window "My App" [--only Save "File"]   (callout boxes)
    python -m automonkey.ai record demo.mp4 --window "My App" --seconds 10    (video, ffmpeg)
    python -m automonkey.ai resize 1280 800 --window "My App"

Exit codes of replay and the documentation commands: 0 ok, 1 a script step or check failed, 2 the
command itself could not run (bad file, window not found, no ffmpeg).

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
    c = sub.add_parser("controls", help="list a window's controls with click points")
    c.add_argument("window")
    c.add_argument("--all", action="store_true", help="include non-interactive elements")
    c.add_argument("--depth", type=int, default=None)
    h = sub.add_parser("history", help="scripts run today, as .amk text")
    h.add_argument("n", type=int, nargs="?", default=20)
    rp = sub.add_parser("replay", help="run saved .amk regression scripts (exit 0 pass, 1 failed, 2 error)")
    rp.add_argument("files", nargs="+")
    rp.add_argument("--var", action="append", default=[], metavar="NAME=VALUE",
                    help="replace ${NAME} in the scripts (repeatable), e.g. the output folder of shots")
    rp.add_argument("--json", metavar="FILE", help="write a machine-readable report")
    rp.add_argument("--no-failure-shot", action="store_true",
                    help="do not save <name>.failure.png when a script fails")
    cp = sub.add_parser("capture", help="native-resolution PNG of one window or a screen region")
    cp.add_argument("file")
    cp.add_argument("--window", help="title, class or id; the active window by default")
    cp.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "W", "H"), help="screen pixels")
    cp.add_argument("--pad", type=int, default=0, help="grow the window picture by N pixels per side")
    bp = sub.add_parser("bounds", help="JSON with the boxes of a window's controls, relative to its capture")
    bp.add_argument("file")
    bp.add_argument("--window")
    bp.add_argument("--only", nargs="+", metavar="NAME", help="only these controls, in this order")
    bp.add_argument("--pad", type=int, default=0)
    vp = sub.add_parser("record", help="video of one window or region (needs ffmpeg)")
    vp.add_argument("file", help=".mp4, .webm or .gif")
    vp.add_argument("--window")
    vp.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    vp.add_argument("--seconds", type=float, required=True)
    vp.add_argument("--fps", type=int, default=15)
    zp = sub.add_parser("resize", help="make a window's visible frame W x H physical pixels")
    zp.add_argument("size", type=int, nargs=2, metavar=("W", "H"))
    zp.add_argument("--window")
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
        return _replay_files(a)
    elif a.cmd in ("capture", "bounds", "record", "resize"):
        return _capture_command(a)
    elif a.cmd == "install-claude":
        return _install_claude(a.config_dir, mcp=not a.no_mcp)
    return 0


def _replay_files(a) -> int:
    import json
    import time
    variables = {}
    for item in a.var:
        name, sep, value = item.partition("=")
        if not sep or not name:
            print(f"--var needs NAME=VALUE, got {item!r}")
            return 2
        variables[name] = value
    failed, errors, report = 0, 0, []
    for path in a.files:
        t0 = time.monotonic()
        try:
            ok, log, _img = replay(path, screenshot_on_failure=not a.no_failure_shot, variables=variables)
        except OSError as e:  # an unreadable script is not the same as a script that failed
            print(f"ERROR: {path}: {e}")
            errors += 1
            report.append(dict(file=path, passed=False, error=str(e), seconds=0.0, log=[]))
            continue
        print(log)
        failed += not ok
        report.append(dict(file=path, passed=ok, error=None, seconds=round(time.monotonic() - t0, 2),
                           log=log.splitlines()))
    passed = len(a.files) - failed - errors
    print(f"{passed} passed, {failed} failed" + (f", {errors} could not run" if errors else ""))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dict(passed=passed, failed=failed, errors=errors, scripts=report), f, indent=2,
                      ensure_ascii=False)
    return 2 if errors else (1 if failed else 0)


def _capture_command(a) -> int:
    """capture / bounds / record / resize: the documentation tools (automonkey/ai/capture.py)."""
    import json
    import time
    from . import capture
    try:
        if a.cmd == "capture":
            img = (capture.capture_region(*a.region) if a.region
                   else capture.capture_window(a.window, a.pad))
            print(f"saved {capture.save_png(img, a.file)} ({img.width}x{img.height})")
        elif a.cmd == "bounds":
            data = capture.control_bounds(a.window, a.only, a.pad)
            path = os.path.abspath(a.file)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"saved {path} ({len(data['controls'])} controls)")
        elif a.cmd == "record":
            print(capture.start_recording(a.file, window=a.window, region=a.region and tuple(a.region), fps=a.fps))
            try:
                time.sleep(a.seconds)
            finally:
                print(capture.stop_recording())
        elif a.cmd == "resize":
            w = capture.resize_window(a.window, *a.size)
            print(f"{w['title']!r} is {w['w']}x{w['h']}")
            return 0 if (w["w"], w["h"]) == tuple(a.size) else 1
    except (capture.CaptureError, LookupError, RuntimeError, TimeoutError) as e:
        print(f"ERROR: {e}")
        return 2
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
