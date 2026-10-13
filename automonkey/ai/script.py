"""A tiny action language so an AI can do many steps in ONE tool call.

One command per line (or separated by ';'; write '\\;' for a literal ';').
Coordinates are image pixels of the latest screenshot.

    click X Y [left|right|middle] [N]   dclick X Y    rclick X Y    move X Y
    drag X1 Y1 X2 Y2                    scroll N [X Y]   (N>0 up, N<0 down)
    type TEXT...                        key K [K...]     hotkey ctrl+shift+t
    wait SECONDS                        stable [TIMEOUT]   change [TIMEOUT]
    launch COMMAND...                   focus WINDOW     maximize [WINDOW]   close WINDOW
    url ADDRESS                         (focus address bar, type, Enter, wait for load)
    click_text TEXT...                  wait_text TEXT...   (OCR, needs tesseract)
    click_image PATH                    (template match)
    press [BUTTON]                      release [BUTTON]
    path X1 Y1 X2 Y2 ...                (freehand: press, glide through every point, release)
"""
from __future__ import annotations

import re
import time

import pyautogui

from . import ocr, screen, windows
from ..key_funcs import hotkey, press, write

pyautogui.PAUSE = 0.03  # default 0.1s per call adds up quickly

INPUT_COMMANDS = {"click", "dclick", "rclick", "move", "drag", "scroll", "type", "key", "hotkey",
                  "url", "click_text", "click_image", "press", "release", "path"}


class StepError(Exception):
    pass


def split_script(script: str) -> list[str]:
    lines = []
    for raw in script.splitlines():
        for part in re.split(r"(?<!\\);", raw):
            part = part.replace("\\;", ";").strip()
            if part and not part.startswith("#"):
                lines.append(part)
    return lines


def _xy(args: list[str], i: int = 0) -> tuple[int, int]:
    try:
        return screen.view().to_input(float(args[i]), float(args[i + 1]))
    except (IndexError, ValueError):
        raise StepError("expected X Y coordinates")


def _keys(spec: str) -> list[str]:
    return [k.strip().lower() for k in re.split(r"[+\s]+", spec) if k.strip()]


def _click_text(text: str):
    hits = ocr.find_text(text)
    if not hits:
        raise StepError(f"text {text!r} not found on screen")
    h = hits[0]
    pyautogui.click(*screen.view().to_input(h["cx"], h["cy"]))
    return f"clicked {h['text']!r} at {h['cx']},{h['cy']}" + (f" ({len(hits)} matches)" if len(hits) > 1 else "")


def run_step(line: str) -> str:
    cmd, _, rest = line.partition(" ")
    cmd = cmd.lower()
    args = rest.split()
    if cmd == "click":
        x, y = _xy(args)
        button = args[2] if len(args) > 2 else "left"
        clicks = int(args[3]) if len(args) > 3 else 1
        pyautogui.click(x, y, clicks=clicks, interval=0.05, button=button)
    elif cmd == "dclick":
        pyautogui.doubleClick(*_xy(args))
    elif cmd == "rclick":
        pyautogui.rightClick(*_xy(args))
    elif cmd == "move":
        pyautogui.moveTo(*_xy(args))
    elif cmd == "drag":
        x1, y1 = _xy(args)
        x2, y2 = _xy(args, 2)
        pyautogui.moveTo(x1, y1)
        pyautogui.dragTo(x2, y2, duration=0.4, button="left")
    elif cmd == "press":
        pyautogui.mouseDown(button=args[0] if args else "left")
    elif cmd == "release":
        pyautogui.mouseUp(button=args[0] if args else "left")
    elif cmd == "path":
        if len(args) < 4 or len(args) % 2:
            raise StepError("path needs an even number of X Y values (at least two points)")
        pts = [_xy(args, i) for i in range(0, len(args), 2)]
        pyautogui.moveTo(*pts[0])
        pyautogui.mouseDown()
        try:
            for p in pts[1:]:
                pyautogui.moveTo(*p, duration=0.02)
        finally:
            pyautogui.mouseUp()
        return f"drew through {len(pts)} points"
    elif cmd == "scroll":
        if len(args) >= 3:
            pyautogui.moveTo(*_xy(args, 1))
        pyautogui.scroll(int(args[0]))
    elif cmd == "type":
        write(rest)
    elif cmd == "key":
        press(args)
    elif cmd == "hotkey":
        hotkey(*_keys(rest))
    elif cmd == "wait":
        time.sleep(float(args[0]) if args else 1.0)
    elif cmd == "stable":
        ok, t = screen.wait_stable(timeout=float(args[0]) if args else 15)
        return f"stable after {t:.1f}s" if ok else f"still changing after {t:.1f}s"
    elif cmd == "change":
        ok, t = screen.wait_change(timeout=float(args[0]) if args else 15)
        return f"changed after {t:.1f}s" if ok else f"no change within {t:.1f}s"
    elif cmd == "url":
        hotkey("ctrl", "l")
        time.sleep(0.15)
        write(rest)
        time.sleep(0.3)  # let the address bar's suggestion list catch up before Enter
        before = screen.grab()  # after typing, so the typed text alone doesn't count as "loaded"
        press("enter")
        changed, _ = screen.wait_change(before, timeout=30)
        if not changed:
            return "no visible change 30s after Enter (still loading, or not navigated)"
        ok, t = screen.wait_stable(timeout=20)
        return f"loaded{'' if ok else ' (still changing)'}"
    elif cmd == "launch":
        w = windows.launch(rest)
        windows.focus(w["id"])
        screen.wait_stable(timeout=20)
        return f"window {w['id']} {w['title']!r}"
    elif cmd == "focus":
        w = windows.focus(rest)
        return f"focused {w['title']!r}"
    elif cmd == "maximize":
        w = windows.maximize(rest or None)
        screen.wait_stable(stable_for=0.5, timeout=5)
        return f"maximized {w['title']!r}"
    elif cmd == "close":
        w = windows.close(rest)
        return f"closed {w['title']!r}"
    elif cmd == "click_text":
        return _click_text(rest)
    elif cmd == "wait_text":
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if ocr.find_text(rest):
                return "text appeared"
            time.sleep(0.5)
        raise StepError(f"text {rest!r} did not appear within 20s")
    elif cmd == "click_image":
        box = pyautogui.locate(rest, screen.grab(), grayscale=True)
        if not box:
            raise StepError(f"image {rest!r} not found on screen")
        cx, cy = screen.view().capture_to_image(box.left + box.width / 2, box.top + box.height / 2)
        pyautogui.click(*screen.view().to_input(cx, cy))
        return f"clicked image at {cx},{cy}"
    else:
        raise StepError(f"unknown command {cmd!r}")
    return "ok"


def run(script: str, settle: bool = True) -> tuple[list[str], bool]:
    """Run every step, stopping at the first failure. Returns (log, success).
    With `settle`, waits for the screen to stop changing after input steps."""
    log, steps = [], split_script(script)
    for n, line in enumerate(steps, 1):
        t0 = time.monotonic()
        try:
            result = run_step(line)
            log.append(f"{n}. {line} -> {result} ({time.monotonic() - t0:.1f}s)")
        except pyautogui.FailSafeException:
            log.append(f"{n}. {line} -> ABORTED: mouse in a screen corner (pyautogui fail-safe)")
            return log, False
        except Exception as e:  # report and stop; the AI decides what to do next
            log.append(f"{n}. {line} -> FAILED: {e}")
            if n < len(steps):
                log.append(f"   skipped {len(steps) - n} remaining step(s)")
            return log, False
    last = steps[-1].split()[0].lower() if steps else ""
    if settle and last in INPUT_COMMANDS:
        ok, t = screen.wait_stable(stable_for=0.6, timeout=10)
        log.append(f"settled in {t:.1f}s" if ok else f"screen still changing after {t:.1f}s")
    return log, True
