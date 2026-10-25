"""AI-friendly layer over AutoMonkey: act + observe in a single call.

    from automonkey.ai import act, observe
    text, img = act("launch firefox; maximize; url google.ro; type betano.ro")

All coordinates are pixels of the screenshot the AI was shown.
"""
from __future__ import annotations

import datetime
import json
import os
import time

from PIL import Image

from . import ocr, screen, windows
from . import script as _script
from .script import run, split_script

SESSION_DIR = os.environ.get("AUTOMONKEY_SESSION_DIR",
                             os.path.join(os.path.expanduser("~"), ".cache", "automonkey", "sessions"))


def _context() -> str:
    v = screen.view()
    try:
        w = windows.active_window()
        active = f"active window: {w['title']!r}"
    except Exception:
        active = "active window: unknown"
    return f"{v.describe()}; {active}"


def observe(grid: int = 0, max_side: int = screen.DEFAULT_MAX_SIDE) -> tuple[str, Image.Image]:
    img = screen.shot(grid=grid, max_side=max_side)
    return _context(), img


def _session_file() -> str:
    return os.path.join(SESSION_DIR, datetime.date.today().isoformat() + ".jsonl")


def _record(script: str, ok: bool, log: list[str]):
    """Append every executed script to today's session log, so a script that found a bug
    can be copied into a regression file later (see `history` and `replay`)."""
    try:
        os.makedirs(SESSION_DIR, exist_ok=True)
        with open(_session_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": time.strftime("%H:%M:%S"), "ok": ok, "script": script, "log": log},
                               ensure_ascii=False) + "\n")
    except OSError:
        pass  # recording is a convenience; never fail an action because of it


def history(n: int = 20) -> str:
    """The last `n` scripts run today, oldest first, as ready-to-save .amk text."""
    try:
        with open(_session_file(), encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except OSError:
        return "no scripts recorded today"
    out = []
    for e in entries[-n:]:
        status = "ok" if e["ok"] else "FAILED: " + (e["log"][-1] if e["log"] else "")
        out.append(f"# {e['time']} {status}")
        out.extend(split_script(e["script"]))
    return "\n".join(out)


def act(script: str, screenshot: bool = True, grid: int = 0, settle: bool = True) -> tuple[str, Image.Image | None]:
    """Run an action script, then report what happened (and show the screen)."""
    before = screen.grab()
    log, ok = run(script, settle=settle)
    _record(script, ok, log)
    after = screen.grab()
    img = screen.shot(grid=grid, full=after) if screenshot else None
    lines = log + [screen.diff_summary(before, after), _context()]
    if not ok:
        lines.insert(0, "STOPPED AT A FAILED STEP")
    return "\n".join(lines), img


def replay(path: str, screenshot_on_failure: bool = True) -> tuple[bool, str, Image.Image | None]:
    """Run a saved .amk regression script. Returns (passed, log, screenshot of the failure).
    On failure the full-resolution screen is also saved next to the script as
    <name>.failure.png, as evidence for the bug report."""
    with open(path, encoding="utf-8") as f:
        script = f.read()
    log, ok = run(script, settle=True)
    img = None
    if not ok and screenshot_on_failure:
        # The screen when the step failed: `finally:` steps may have closed the app since.
        full = _script.failure_image or screen.grab()
        evidence = os.path.splitext(path)[0] + ".failure.png"
        try:
            full.save(evidence)
            log.append(f"failure screenshot: {evidence}")
        except OSError:
            pass
        img = screen.shot(full=full)
    head = f"{'PASSED' if ok else 'FAILED'}: {path}"
    return ok, "\n".join([head] + log), img


def window_list() -> str:
    v = screen.view()
    out = []
    for w in windows.list_windows():
        if w.get("minimized"):
            where = "minimized"
        else:
            x, y = v.to_image(w["x"], w["y"])
            r, b = v.to_image(w["x"] + w["w"], w["y"] + w["h"])
            where = f"x={x}..{r} y={y}..{b}"
        out.append(f"{'*' if w['active'] else ' '} {w['id']:>10}  {w['title']!r}  [{w['wm_class']}]  {where}")
    return "\n".join(out) or "no windows"


__all__ = ["act", "observe", "window_list", "history", "replay", "ocr", "screen", "windows", "run",
           "split_script"]
