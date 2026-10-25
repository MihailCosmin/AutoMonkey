"""A tiny action language so an AI can do many steps in ONE tool call.

One command per line (or separated by ';'; write '\\;' for a literal ';'). Lines that
start with '#' are comments. Coordinates are image pixels of the latest screenshot.

Mouse (real input events: hover, drags and strokes reach every app):
    click X Y [left|right|middle] [N]   dclick X Y    rclick X Y    mclick X Y
    move X Y      (glides there: hover effects and tooltips fire)
    drag X1 Y1 X2 Y2 [button]           (press, glide, release - drag-and-drop, sliders, splitters)
    path X1 Y1 X2 Y2 ...                (press, glide through every point, release: freehand)
    stroke X1 Y1 X2 Y2 ...              (same as path)
    press [BUTTON]    release [BUTTON]  (hold a button across other steps)
    scroll N [X Y]    hscroll N [X Y]   (N>0 up / right, N<0 down / left)
Keyboard:
    type TEXT...      key K [K...]      hotkey ctrl+shift+t
    keydown K         keyup K           (hold a key, e.g. keydown ctrl; click ...; keyup ctrl)
Waiting:
    wait SECONDS      stable [TIMEOUT]  change [TIMEOUT]
Windows and apps:
    launch COMMAND... focus WINDOW      maximize [WINDOW]   close WINDOW   monitor N
    kill WINDOW       (end the window's process - ONLY for an app the test itself launched)
Lines after a line `finally:` always run, even after a failure: close the app under test there.
    url ADDRESS                         (focus address bar, type, Enter, wait for load)
Finding things:
    click_text TEXT...                  wait_text TEXT...   (OCR, needs tesseract)
    click_image PATH                    (template match)
    click_control NAME [in WINDOW]      (accessibility tree; real mouse click on its centre)
    drag_control NAME to NAME [in WINDOW]  (drag-and-drop between two controls' centres)
    focused                             (which control has the keyboard focus)
    tab_order N [shift]                 (press Tab N times, report the focused control each time)
    clipped [WINDOW]                    (labels whose text is cut off: accessibility name vs OCR)
Text steps (click_text, wait_text, expect_text, expect_no_text) read only the ACTIVE
window, so text elsewhere (a terminal showing this very script) can't match; prefix the
text with "screen:" to search the whole screen, e.g. `expect_text screen: Saved`.
Checks (a failed check stops the script - use them in saved regression scripts):
    expect_text TEXT...       expect_no_text TEXT...      expect_window TITLE
    expect_no_window TITLE    expect_focus NAME           expect_control NAME [in WINDOW]
    expect_change [TIMEOUT]   (the screen changed since before the previous input step)
    expect_no_clipped [WINDOW]
    expect_order NAME, NAME, ... [in WINDOW]   (controls appear top-to-bottom in this order)
Evidence:
    save PATH                 (save a full-resolution screenshot, e.g. for a bug report)
"""
from __future__ import annotations

import os
import re
import sys
import time

import pyautogui

from . import inject, ocr, screen, windows
from ..key_funcs import hotkey, press, write

pyautogui.PAUSE = 0.03  # default 0.1s per call adds up quickly

INPUT_COMMANDS = {"click", "dclick", "rclick", "mclick", "move", "drag", "scroll", "hscroll", "type", "key",
                  "hotkey", "url", "click_text", "click_image", "click_control", "press", "release", "path",
                  "stroke", "keydown", "keyup", "tab_order", "drag_control"}


class StepError(Exception):
    pass


class _State:
    """Per-run state: keys held with keydown, and the screen before the last input step
    (captured only when the script uses expect_change)."""

    def __init__(self):
        self.keys_held: list[str] = []
        self.track_input = False
        self.before_input = None


_state = _State()


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


def _points(args: list[str]) -> list[tuple[int, int]]:
    if len(args) < 4 or len(args) % 2:
        raise StepError("needs an even number of X Y values (at least two points)")
    return [_xy(args, i) for i in range(0, len(args), 2)]


def _keys(spec: str) -> list[str]:
    return [k.strip().lower() for k in re.split(r"[+\s]+", spec) if k.strip()]


def _name_in_window(rest: str) -> tuple[str, str | int]:
    """'Save in Notepad' -> ('Save', 'Notepad'); 'Save' -> ('Save', <active window>)."""
    m = re.match(r"(.+?)\s+in\s+(.+)$", rest)
    if m:
        return m.group(1).strip().strip('"'), m.group(2).strip().strip('"')
    return rest.strip().strip('"'), windows.active_window()["id"]


def _text_scope(rest: str) -> tuple[str, tuple[int, int, int, int] | None, str]:
    """('screen: Saved') -> ('Saved', None, 'on screen'); otherwise the active window's box."""
    text = rest.strip()
    if text.lower().startswith("screen:"):
        return text[7:].strip(), None, "on screen"
    try:
        w = windows.active_window()
    except LookupError:
        return text, None, "on screen"
    if w.get("minimized"):
        return text, None, "on screen"
    v = screen.view()
    x0, y0 = v.to_image(w["x"], w["y"])
    x1, y1 = v.to_image(w["x"] + w["w"], w["y"] + w["h"])
    return text, (x0, y0, x1 - x0, y1 - y0), f"in {w['title']!r}"


def _find_text(rest: str) -> tuple[list[dict], str, str]:
    """OCR first; on Windows, text OCR can't read (tiny or low-contrast fonts) is then
    looked up among the names of the active window's visible controls, which are the
    texts the app draws."""
    text, region, where = _text_scope(rest)
    hits = ocr.find_text(text, region=region)
    if hits or region is None or sys.platform != "win32":
        return hits, text, where
    from . import controls
    want = controls.normalize(text)
    try:
        for _level, _ei, p in controls.walk(windows.active_window()["id"]):
            if p["rect"] and want in controls.normalize(p["name"]):
                x, y, w, h = p["rect"]
                return [dict(text=p["name"], x=x, y=y, w=w, h=h, cx=x + w // 2, cy=y + h // 2, exact=False)], \
                    text, where + " (accessibility tree; OCR could not read it)"
    except Exception:
        pass
    return hits, text, where


def _click_text(rest: str):
    hits, text, where = _find_text(rest)
    if not hits:
        raise StepError(f"text {text!r} not found {where}")
    h = hits[0]
    inject.click(*screen.view().to_input(h["cx"], h["cy"]))
    return f"clicked {h['text']!r} at {h['cx']},{h['cy']}" + (f" ({len(hits)} matches)" if len(hits) > 1 else "")


def _focus_text() -> str:
    from . import controls
    return controls.describe(controls.focused())


# How long expect_* checks keep retrying: apps update the screen asynchronously, so a
# check made right after a click may run before the next frame is painted.
EXPECT_TIMEOUT = float(os.environ.get("AUTOMONKEY_EXPECT_TIMEOUT", "3"))


def run_step(line: str) -> str:
    cmd = line.partition(" ")[0].lower()
    if not cmd.startswith("expect_") or cmd == "expect_change":
        return _run_step(line)
    deadline = time.monotonic() + EXPECT_TIMEOUT
    while True:
        try:
            return _run_step(line)
        except StepError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.3)


def _run_step(line: str) -> str:
    cmd, _, rest = line.partition(" ")
    cmd = cmd.lower()
    args = rest.split()
    if cmd in INPUT_COMMANDS and _state.track_input:
        _state.before_input = screen.grab()
    if cmd == "click":
        x, y = _xy(args)
        button = args[2] if len(args) > 2 else "left"
        clicks = int(args[3]) if len(args) > 3 else 1
        inject.click(x, y, button=button, clicks=clicks)
    elif cmd == "dclick":
        inject.click(*_xy(args), clicks=2)
    elif cmd == "rclick":
        inject.click(*_xy(args), button="right")
    elif cmd == "mclick":
        inject.click(*_xy(args), button="middle")
    elif cmd == "move":
        inject.move_to(*_xy(args))
    elif cmd == "drag":
        if len(args) < 4:
            raise StepError("drag needs X1 Y1 X2 Y2")
        inject.drag([_xy(args), _xy(args, 2)], button=args[4] if len(args) > 4 else "left")
        return "dragged"
    elif cmd == "press":
        inject.press(args[0] if args else "left")
    elif cmd == "release":
        inject.release(args[0] if args else "left")
    elif cmd in ("path", "stroke"):
        pts = _points(args)
        inject.drag(pts, hold=0.1)
        return f"drew through {len(pts)} points"
    elif cmd in ("scroll", "hscroll"):
        if not args:
            raise StepError(f"{cmd} needs N")
        xy = _xy(args, 1) if len(args) >= 3 else (None, None)
        inject.scroll(int(args[0]), *xy, horizontal=cmd == "hscroll")
    elif cmd == "type":
        write(rest)
    elif cmd == "key":
        press(args)
    elif cmd == "hotkey":
        hotkey(*_keys(rest))
    elif cmd == "keydown":
        for k in _keys(rest):
            pyautogui.keyDown(k, _pause=False)
            _state.keys_held.append(k)
    elif cmd == "keyup":
        for k in _keys(rest):
            pyautogui.keyUp(k, _pause=False)
            if k in _state.keys_held:
                _state.keys_held.remove(k)
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
        reused = w.get("reused")
        w = windows.focus(w["id"])
        screen.wait_stable(timeout=20)
        if reused:
            # Stop before the next step can type into the user's own documents.
            raise StepError(f"{rest!r} reused the window {w['id']} {w['title']!r} that was already open (or "
                            "hidden): it may hold the user's own documents. Nothing more was done. Look at the "
                            "screenshot; open a fresh document in it first (e.g. hotkey ctrl+n), or ask the "
                            "user to close the app.")
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
    elif cmd == "kill":
        w = windows.kill(rest)
        return f"ended the process of {w['title']!r} ({w['wm_class'] or 'pid ' + str(w.get('pid'))})"
    elif cmd == "monitor":
        index = int(args[0]) if args else 0
        x, y, w, h = screen.set_monitor(index)
        return f"now on monitor {index}: {w}x{h} at {x},{y} (take a new screenshot)"
    elif cmd == "click_text":
        return _click_text(rest)
    elif cmd == "wait_text":
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            hits, text, where = _find_text(rest)
            if hits:
                return f"text appeared {where}"
            time.sleep(0.5)
        raise StepError(f"text {text!r} did not appear {where} within 20s")
    elif cmd == "click_image":
        box = pyautogui.locate(rest, screen.grab(), grayscale=True)
        if not box:
            raise StepError(f"image {rest!r} not found on screen")
        cx, cy = screen.view().capture_to_image(box.left + box.width / 2, box.top + box.height / 2)
        inject.click(*screen.view().to_input(cx, cy))
        return f"clicked image at {cx},{cy}"
    elif cmd == "click_control":
        from . import controls
        name, win = _name_in_window(rest)
        p = controls.find(win, name)
        if not p["rect"]:
            raise StepError(f"control {name!r} has no on-screen box (hidden, collapsed or scrolled away)")
        x, y, w, h = p["rect"]
        inject.click(*screen.view().to_input(x + w / 2, y + h / 2))
        return f"clicked {controls.describe(p)}" + ("" if p["enabled"] else " (it is DISABLED)")
    elif cmd == "drag_control":
        from . import controls
        names, win = _name_in_window(rest)
        if " to " not in names:
            raise StepError("drag_control needs: SOURCE to TARGET [in WINDOW]")
        src_name, dst_name = (n.strip().strip('"') for n in names.split(" to ", 1))
        ends = []
        for n in (src_name, dst_name):
            p = controls.find(win, n)
            if not p["rect"]:
                raise StepError(f"control {n!r} has no on-screen box")
            x, y, w, h = p["rect"]
            ends.append(screen.view().to_input(x + w / 2, y + h / 2))
        inject.drag(ends)
        return f"dragged {src_name!r} onto {dst_name!r}"
    elif cmd == "expect_order":
        from . import controls
        names, win = _name_in_window(rest)
        wanted = [n.strip().strip('"') for n in names.split(",") if n.strip()]
        boxes = []
        for n in wanted:
            p = controls.find(win, n)
            if not p["rect"]:
                raise StepError(f"control {n!r} has no on-screen box")
            boxes.append((p["rect"][1], p["rect"][0], n))
        actual = [n for _y, _x, n in sorted(boxes)]
        if actual != wanted:
            raise StepError(f"order on screen is {', '.join(actual)}; expected {', '.join(wanted)}")
        return "order ok"
    elif cmd == "focused":
        return _focus_text()
    elif cmd in ("clipped", "expect_no_clipped"):
        from . import controls
        found = controls.clipped(rest.strip() or windows.active_window()["id"])
        report = "clipped text:\n      " + "\n      ".join(found)
        if found and cmd == "expect_no_clipped":
            raise StepError(report)
        return report if found else "no clipped text found"
    elif cmd == "tab_order":
        n = int(args[0]) if args else 10
        back = len(args) > 1 and args[1].lower().startswith("shift")
        seen = [f"start: {_focus_text()}"]
        for i in range(1, n + 1):
            if back:
                hotkey("shift", "tab")
            else:
                press("tab")
            time.sleep(0.2)
            seen.append(f"{i}: {_focus_text()}")
        return "focus order:\n      " + "\n      ".join(seen)
    elif cmd == "expect_text":
        hits, text, where = _find_text(rest)
        if not hits:
            raise StepError(f"expected text {text!r} is not {where}")
        return f"text present {where} at {hits[0]['cx']},{hits[0]['cy']}"
    elif cmd == "expect_no_text":
        hits, text, where = _find_text(rest)
        if hits:
            raise StepError(f"text {text!r} is {where} (at {hits[0]['cx']},{hits[0]['cy']}) but should not be")
        return f"text absent {where}"
    elif cmd == "expect_window":
        try:
            w = windows.find_window(rest)
        except LookupError as e:
            raise StepError(str(e))
        return f"window {w['title']!r} exists"
    elif cmd == "expect_no_window":
        try:
            w = windows.find_window(rest)
        except LookupError:
            return "no such window"
        raise StepError(f"window {w['title']!r} exists but should not")
    elif cmd == "expect_focus":
        from . import controls
        f = controls.focused()
        want = controls.normalize(rest)
        if want not in controls.normalize(f["name"]) and rest.strip().lower() != f["auto_id"].lower():
            raise StepError(f"focus is on {controls.describe(f)}, expected {rest!r}")
        return f"focus on {f['name']!r}"
    elif cmd == "expect_control":
        from . import controls
        name, win = _name_in_window(rest)
        try:
            p = controls.find(win, name)
        except LookupError as e:
            raise StepError(str(e))
        return f"found {controls.describe(p)}"
    elif cmd == "expect_change":
        if _state.before_input is None:
            raise StepError("expect_change needs an input step before it")
        ok, t = screen.wait_change(_state.before_input, timeout=float(args[0]) if args else 3)
        if not ok:
            raise StepError(f"the screen did not change within {t:.1f}s of the previous input step")
        return f"changed ({t:.1f}s)"
    elif cmd == "save":
        if not rest:
            raise StepError("save needs a file path")
        path = os.path.abspath(os.path.expanduser(rest.strip().strip('"')))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        screen.grab().save(path)
        return f"saved {path}"
    else:
        raise StepError(f"unknown command {cmd!r}")
    return "ok"


def _cleanup():
    """Never leave a mouse button or a modifier key held down after a script."""
    inject.release_all()
    for k in reversed(_state.keys_held):
        try:
            pyautogui.keyUp(k, _pause=False)
        except Exception:
            pass
    _state.keys_held.clear()


# Screenshot taken at the moment a step failed (before any `finally:` steps ran), for
# bug reports; None after a successful run.
failure_image = None


def run(script: str, settle: bool = True) -> tuple[list[str], bool]:
    """Run every step, stopping at the first failure. Returns (log, success).
    Steps after a line `finally:` always run, also after a failure (close the app under
    test there); a failing `finally:` step is logged but doesn't change the result.
    With `settle`, waits for the screen to stop changing after input steps."""
    global failure_image
    log, steps = [], split_script(script)
    split = next((i for i, s in enumerate(steps) if s.lower() == "finally:"), len(steps))
    main, final = steps[:split], steps[split + 1:]
    _state.track_input = any(s.split()[0].lower() == "expect_change" for s in steps)
    _state.before_input = None
    failure_image = None
    ok = True
    try:
        for n, line in enumerate(main, 1):
            t0 = time.monotonic()
            try:
                result = run_step(line)
                log.append(f"{n}. {line} -> {result} ({time.monotonic() - t0:.1f}s)")
            except pyautogui.FailSafeException:
                log.append(f"{n}. {line} -> ABORTED: mouse in a screen corner (fail-safe)")
                return log, False  # the user wants control back: skip `finally:` too
            except Exception as e:  # report and stop; the AI decides what to do next
                log.append(f"{n}. {line} -> FAILED: {e}")
                if n < len(main):
                    log.append(f"   skipped {len(main) - n} remaining step(s)")
                ok = False
                try:
                    failure_image = screen.grab()
                except Exception:
                    pass
                break
    finally:
        _cleanup()
    if final:
        log.append("finally:")
        for n, line in enumerate(final, len(main) + 1):
            try:
                log.append(f"{n}. {line} -> {run_step(line)}")
            except Exception as e:
                log.append(f"{n}. {line} -> failed (ignored in finally): {e}")
        _cleanup()
    last = steps[-1].split()[0].lower() if steps else ""
    if ok and settle and last in INPUT_COMMANDS:
        stable, t = screen.wait_stable(stable_for=0.6, timeout=10)
        log.append(f"settled in {t:.1f}s" if stable else f"screen still changing after {t:.1f}s")
    return log, ok
