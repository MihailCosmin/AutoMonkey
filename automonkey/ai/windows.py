"""Launching apps and finding / focusing windows.

Linux uses xdotool + wmctrl. On Wayland, pyautogui input only reaches X11
(XWayland) windows, so `launch` forces apps onto X11 automatically.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import time

from .screen import session_type

# Env vars that make common toolkits use X11 instead of native Wayland.
X11_ENV = {
    "MOZ_ENABLE_WAYLAND": "0",           # Firefox / Thunderbird
    "GDK_BACKEND": "x11",                # GTK
    "QT_QPA_PLATFORM": "xcb",            # Qt
    "SDL_VIDEODRIVER": "x11",            # SDL
    "ELECTRON_OZONE_PLATFORM_HINT": "x11",
}
CHROMIUM_LIKE = ("chromium", "chromium-browser", "google-chrome", "chrome", "code", "brave-browser")


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout


def _require_linux_tools():
    missing = [t for t in ("xdotool", "wmctrl") if not shutil.which(t)]
    if missing:
        raise RuntimeError(f"missing tools: {', '.join(missing)} (sudo apt install {' '.join(missing)})")


def list_windows() -> list[dict]:
    """Visible top-level windows: id, title, wm_class, x, y, w, h, active."""
    if sys.platform == "win32":
        import pygetwindow as gw
        active = gw.getActiveWindow()
        return [dict(id=w._hWnd, title=w.title, wm_class="", x=w.left, y=w.top, w=w.width, h=w.height,
                     active=active is not None and w._hWnd == active._hWnd)
                for w in gw.getAllWindows() if w.title and w.visible]
    _require_linux_tools()
    active = _run("xdotool", "getactivewindow").strip()
    wins = []
    for line in _run("wmctrl", "-lGx").splitlines():
        parts = line.split(None, 8)
        if len(parts) < 8:
            continue
        wid, _desk, x, y, w, h, wm_class = parts[:7]
        title = parts[8] if len(parts) > 8 else ""
        wins.append(dict(id=int(wid, 16), title=title, wm_class=wm_class, x=int(x), y=int(y),
                         w=int(w), h=int(h), active=active.isdigit() and int(active) == int(wid, 16)))
    return wins


def find_window(query: str | int) -> dict:
    """Window whose id equals `query`, or whose title / class contains it (case-insensitive)."""
    wins = list_windows()
    if isinstance(query, int) or str(query).isdigit():
        for w in wins:
            if w["id"] == int(query):
                return w
    q = str(query).lower()
    matches = [w for w in wins if q in w["title"].lower() or q in w["wm_class"].lower()]
    if not matches:
        titles = "; ".join(w["title"] for w in wins) or "none"
        raise LookupError(f"no window matching {query!r}. Open windows: {titles}")
    return next((w for w in matches if w["active"]), matches[-1])


def focus(query: str | int) -> dict:
    w = find_window(query)
    if sys.platform == "win32":
        import pygetwindow as gw
        gw.Win32Window(w["id"]).activate()
    else:
        subprocess.run(["xdotool", "windowactivate", "--sync", str(w["id"])], capture_output=True, timeout=5)
    time.sleep(0.2)
    return w


def maximize(query: str | int | None = None) -> dict:
    w = find_window(query) if query is not None else active_window()
    if sys.platform == "win32":
        import pygetwindow as gw
        gw.Win32Window(w["id"]).maximize()
    else:
        subprocess.run(["wmctrl", "-i", "-r", hex(w["id"]), "-b", "add,maximized_vert,maximized_horz"],
                       capture_output=True)
    time.sleep(0.5)
    return find_window(w["id"])


def close(query: str | int) -> dict:
    w = find_window(query)
    if sys.platform == "win32":
        import pygetwindow as gw
        gw.Win32Window(w["id"]).close()
    else:
        subprocess.run(["wmctrl", "-i", "-c", hex(w["id"])], capture_output=True)
    return w


def active_window() -> dict:
    for w in list_windows():
        if w["active"]:
            return w
    raise LookupError("no active window")


def launch(command: str, timeout: float = 60.0) -> dict:
    """Start `command` detached and return its first new window once it is visible."""
    before = {w["id"] for w in list_windows()}
    args = shlex.split(command)
    env = dict(os.environ)
    if session_type() == "wayland":
        env.update(X11_ENV)
        if os.path.basename(args[0]) in CHROMIUM_LIKE:
            args.insert(1, "--ozone-platform=x11")
    kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        new = [w for w in list_windows() if w["id"] not in before]
        if new:
            return new[-1]
        time.sleep(0.3)
    raise TimeoutError(f"no new window appeared within {timeout:.0f}s after launching {command!r} "
                       f"(on Wayland the app may have opened as a native window that can't be controlled)")


def format_windows(wins: list[dict]) -> str:
    return "\n".join(f"{'*' if w['active'] else ' '} {w['id']:>10}  {w['wm_class'][:30]:<30} {w['title']}"
                     for w in wins) or "no windows"
