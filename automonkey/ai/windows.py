"""Launching apps and finding / focusing windows.

Linux uses xdotool + wmctrl. On Wayland, pyautogui input only reaches X11
(XWayland) windows, so `launch` forces apps onto X11 automatically.
"""
from __future__ import annotations

import os
import re
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
# Make apps expose their accessibility tree (AT-SPI) to `controls`: Qt only does it on
# request; NO_AT_BRIDGE=1 (removed in `launch`) silently disables it for GTK.
ACCESSIBILITY_ENV = {"QT_LINUX_ACCESSIBILITY_ALWAYS_ON": "1"}
FIREFOX_LIKE = ("firefox", "firefox-esr", "thunderbird")
CHROMIUM_LIKE = ("chromium", "chromium-browser", "google-chrome", "chrome", "code", "brave-browser")


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout


def _require_linux_tools():
    missing = [t for t in ("xdotool", "wmctrl") if not shutil.which(t)]
    if missing:
        raise RuntimeError(f"missing tools: {', '.join(missing)} (sudo apt install {' '.join(missing)})")


# --- Windows ----------------------------------------------------------------
# Native Win32 calls instead of pygetwindow: pygetwindow lists cloaked windows (suspended
# UWP apps, other virtual desktops) as visible, reports frame rectangles that include the
# invisible resize borders, has no process name to match on, and its activate() fails
# silently (or raises "error 0") when another process owns the foreground.
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _adv = ctypes.WinDLL("advapi32", use_last_error=True)
    _dwm = ctypes.WinDLL("dwmapi")
    _ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    _u32.GetAncestor.restype = wintypes.HWND
    _u32.GetForegroundWindow.restype = wintypes.HWND
    _u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _k32.OpenProcess.restype = wintypes.HANDLE
    GA_ROOTOWNER = 3
    DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CLOAKED = 9, 14
    GWL_EXSTYLE, WS_EX_TOOLWINDOW = -20, 0x80
    SW_RESTORE, SW_MAXIMIZE = 9, 3
    WM_CLOSE = 0x0010
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _exe_cache: dict[int, str] = {}

    def _title(hwnd) -> str:
        n = _u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        _u32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

    def _pid(hwnd) -> int:
        pid = wintypes.DWORD()
        _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def _exe(pid: int) -> str:
        if pid in _exe_cache:
            return _exe_cache[pid]
        name = ""
        h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if h:
            try:
                size = wintypes.DWORD(1024)
                buf = ctypes.create_unicode_buffer(size.value)
                if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    name = os.path.basename(buf.value)
            finally:
                _k32.CloseHandle(h)
        _exe_cache[pid] = name
        return name

    def _cloaked(hwnd) -> bool:
        v = wintypes.DWORD()
        return (_dwm.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), ctypes.sizeof(v)) == 0
                and v.value != 0)

    def _rect(hwnd) -> tuple[int, int, int, int]:
        r = wintypes.RECT()
        if _dwm.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) != 0:
            _u32.GetWindowRect(hwnd, ctypes.byref(r))
        return r.left, r.top, r.right - r.left, r.bottom - r.top

    def _root(hwnd) -> int:
        return int(_u32.GetAncestor(hwnd, GA_ROOTOWNER) or hwnd or 0)

    def _foreground() -> int:
        return int(_u32.GetForegroundWindow() or 0)

    def _win32_windows() -> list[dict]:
        fg = _foreground()
        found = []

        def cb(hwnd, _lp):
            if not _u32.IsWindowVisible(hwnd) or _cloaked(hwnd):
                return True
            title = _title(hwnd)
            if not title or _u32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            x, y, w, h = _rect(hwnd)
            if w <= 0 or h <= 0:
                return True
            pid = _pid(hwnd)
            found.append(dict(id=int(hwnd), title=title, wm_class=_exe(pid), pid=pid, x=x, y=y, w=w, h=h,
                              active=int(hwnd) == fg, minimized=bool(_u32.IsIconic(hwnd))))
            return True

        _u32.EnumWindows(_ENUMPROC(cb), 0)
        return found  # z-order: topmost first

    def _all_window_ids() -> set[int]:
        """Every top-level window, hidden and cloaked ones included."""
        ids = set()

        def cb(hwnd, _lp):
            ids.add(int(hwnd))
            return True

        _u32.EnumWindows(_ENUMPROC(cb), 0)
        return ids

    def _alt_tap():
        # Windows only lets the process that received the last input event take the
        # foreground. Injecting a (harmless) Alt press makes this process that one.
        _u32.keybd_event(0x12, 0, 0, 0)
        _u32.keybd_event(0x12, 0, 2, 0)

    def win32_focus(hwnd: int, timeout: float = 2.0) -> bool:
        """Bring `hwnd` to the foreground and VERIFY it got there (it, or a dialog it owns)."""
        if _u32.IsIconic(hwnd):
            _u32.ShowWindow(hwnd, SW_RESTORE)
        target = _root(hwnd)
        deadline = time.monotonic() + timeout
        attempt = 0
        while True:
            fg = _foreground()
            if fg and _root(fg) == target:
                return True
            if time.monotonic() > deadline:
                return False
            if attempt >= 1:
                _alt_tap()
            me = _k32.GetCurrentThreadId()
            other = _u32.GetWindowThreadProcessId(fg, None) if fg else 0
            attached = bool(other) and other != me and bool(_u32.AttachThreadInput(me, other, True))
            try:
                _u32.BringWindowToTop(hwnd)
                _u32.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    _u32.AttachThreadInput(me, other, False)
            attempt += 1
            time.sleep(0.15)

    def process_elevated(pid: int) -> bool | None:
        """True if the process runs elevated (as administrator); None if unknown."""
        h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return None
        try:
            token = wintypes.HANDLE()
            if not _adv.OpenProcessToken(h, 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
                return True  # elevated tokens are usually unreadable from a normal process
            try:
                elev, size = wintypes.DWORD(), wintypes.DWORD()
                ok = _adv.GetTokenInformation(token, 20, ctypes.byref(elev),  # TokenElevation
                                              ctypes.sizeof(elev), ctypes.byref(size))
                return bool(elev.value) if ok else None
            finally:
                _k32.CloseHandle(token)
        finally:
            _k32.CloseHandle(h)

    def self_elevated() -> bool:
        return bool(process_elevated(os.getpid()))


def list_windows() -> list[dict]:
    """Visible top-level windows: id, title, wm_class, x, y, w, h, active."""
    if sys.platform == "win32":
        return _win32_windows()
    _require_linux_tools()
    active = _run("xdotool", "getactivewindow").strip()
    wins = []
    for line in _run("wmctrl", "-lGpx").splitlines():
        parts = line.split(None, 9)
        if len(parts) < 9:
            continue
        wid, _desk, pid, x, y, w, h, wm_class = parts[:8]
        title = parts[9] if len(parts) > 9 else ""
        wins.append(dict(id=int(wid, 16), title=title, wm_class=wm_class, pid=int(pid), x=int(x), y=int(y),
                         w=int(w), h=int(h), active=active.isdigit() and int(active) == int(wid, 16)))
    return wins


def find_window(query: str | int) -> dict:
    """Window whose id equals `query`, or whose title / class contains it (case-insensitive).
    On Windows the class is the process name (e.g. `mspaint.exe`), which survives title
    changes such as "Untitled - Paint" -> "drawing.png - Paint"."""
    wins = list_windows()
    if isinstance(query, int) or str(query).isdigit():
        for w in wins:
            if w["id"] == int(query):
                return w
    q = str(query).lower()
    matches = [w for w in wins if q in w["title"].lower() or q in w["wm_class"].lower()]
    if not matches:
        titles = "; ".join(w["title"] for w in wins) or "none"
        raise LookupError(f"no window matching {query!r} (is the app running? start it with `launch`). "
                          f"Open windows: {titles}")
    if sys.platform == "win32":
        return next((w for w in matches if w["active"]), matches[0])  # else the topmost one
    return next((w for w in matches if w["active"]), matches[-1])


def focus(query: str | int) -> dict:
    w = find_window(query)
    if sys.platform == "win32":
        if not win32_focus(w["id"]):
            fg = active_window_or_none()
            hint = ""
            if process_elevated(w["pid"]) and not self_elevated():
                hint = (" The window belongs to an elevated (administrator) process; Windows blocks input "
                        "to it from a normal process. Run AutoMonkey elevated, or the app non-elevated.")
            fg_title = fg["title"] if fg else "unknown"
            raise RuntimeError(f"could not bring {w['title']!r} to the foreground (the foreground is "
                               f"{fg_title!r}).{hint}")
        return find_window(w["id"])
    else:
        subprocess.run(["xdotool", "windowactivate", "--sync", str(w["id"])], capture_output=True, timeout=5)
    time.sleep(0.2)
    return w


def maximize(query: str | int | None = None) -> dict:
    w = find_window(query) if query is not None else active_window()
    if sys.platform == "win32":
        _u32.ShowWindow(w["id"], SW_MAXIMIZE)
    else:
        subprocess.run(["wmctrl", "-i", "-r", hex(w["id"]), "-b", "add,maximized_vert,maximized_horz"],
                       capture_output=True)
    time.sleep(0.5)
    return find_window(w["id"])


def close(query: str | int) -> dict:
    w = find_window(query)
    if sys.platform == "win32":
        _u32.PostMessageW(w["id"], WM_CLOSE, 0, 0)
    else:
        subprocess.run(["wmctrl", "-i", "-c", hex(w["id"])], capture_output=True)
    return w


def kill(query: str | int) -> dict:
    """End the process that owns the window (unsaved work in it is lost). For apps a test
    launched itself, when `close` can't work, e.g. while a modal dialog is open."""
    w = find_window(query)
    if sys.platform == "win32":
        h = _k32.OpenProcess(0x0001, False, w["pid"])  # PROCESS_TERMINATE
        if not h:
            raise RuntimeError(f"cannot end the process of {w['title']!r} (access denied)")
        try:
            _k32.TerminateProcess(h, 1)
        finally:
            _k32.CloseHandle(h)
    else:
        pid = _run("xdotool", "getwindowpid", str(w["id"])).strip()
        if not pid.isdigit():
            raise RuntimeError(f"cannot find the process of {w['title']!r}")
        import signal
        os.kill(int(pid), signal.SIGTERM)
    return w


def active_window() -> dict:
    w = active_window_or_none()
    if w is None:
        raise LookupError("no active window")
    return w


def active_window_or_none() -> dict | None:
    wins = list_windows()
    for w in wins:
        if w["active"]:
            return w
    if sys.platform == "win32":
        fg = _foreground()  # the foreground may be an untitled popup: report its owner
        if fg:
            return next((w for w in wins if w["id"] == _root(fg)), None)
    return None


PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "automonkey", "profiles")

# Quiet automation profile: no first-run tabs, default-browser nags or translation popups.
FIREFOX_PREFS = """\
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("datareporting.policy.firstRunURL", "");
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.translations.automaticallyPopup", false);
user_pref("browser.translations.panelShown", true);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.sessionstore.resume_from_crash", false);
"""


def _separate_browser_instance(args: list[str]) -> list[str]:
    """Browsers hand a launch over to an already running instance of the same profile.
    If the user's own browser runs as a native Wayland window, our window would end
    up there and be uncontrollable, so use a dedicated automation profile instead.
    Relaunching later reuses that (X11) instance, which is what we want."""
    name = os.path.basename(args[0])
    if name in FIREFOX_LIKE and not {"-P", "--profile", "-profile"} & set(args):
        path = os.path.join(PROFILE_DIR, name)
        os.makedirs(path, exist_ok=True)
        user_js = os.path.join(path, "user.js")
        if not os.path.exists(user_js):
            with open(user_js, "w", encoding="utf-8") as f:
                f.write(FIREFOX_PREFS)
        return [args[0], "--profile", path, *args[1:]]
    if name in CHROMIUM_LIKE:
        extra = ["--ozone-platform=x11"]
        if not any(a.startswith("--user-data-dir") for a in args):
            path = os.path.join(PROFILE_DIR, name)
            os.makedirs(path, exist_ok=True)
            extra.append(f"--user-data-dir={path}")
        return [args[0], *extra, *args[1:]]
    return args


def launch(command: str, timeout: float = 60.0) -> dict:
    """Start `command` detached and return its first new window once it is visible."""
    before = {w["id"] for w in list_windows()}
    if sys.platform == "win32":
        return _win32_launch(command, before, timeout)
    args = shlex.split(_posix_command(command))
    env = dict(os.environ)
    env.update(ACCESSIBILITY_ENV)
    env.pop("NO_AT_BRIDGE", None)
    if session_type() == "wayland":
        env.update(X11_ENV)
        args = _separate_browser_instance(args)
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


_WIN_VENV_PYTHON = re.compile(r"^(?P<venv>[^\s\"]*?)[\\/]Scripts[\\/]pythonw?(?:\.exe)?(?=\s|$)", re.I)


def _posix_command(command: str) -> str:
    """Lets a script written on Windows launch the same program on Linux: a venv's
    `X\\Scripts\\python(w).exe` becomes `X/bin/python`, and backslashes in relative paths
    (`tests\\apps\\qt_target.py`) become slashes. Only commands that start with such a
    venv interpreter are touched, so shell escapes in other commands keep working."""
    m = _WIN_VENV_PYTHON.match(command.strip())
    if not m:
        return command
    rest = command.strip()[m.end():]
    return m.group("venv").replace("\\", "/") + "/bin/python" + rest.replace("\\", "/")


def _win32_launch(command: str, before: set, timeout: float) -> dict:
    """Windows: CreateProcess parses the command line itself (shlex would eat the
    backslashes of a path). Names it can't run directly - App Execution Aliases of Store
    apps, documents, `explorer shell:AppsFolder\\<AppID>` - go through the shell (`start`).
    Single-instance apps (Windows 11 Notepad, Explorer, VS Code, browsers) hand the launch
    to a window that already exists; that window is accepted when it comes to the front.

    The returned window gets `reused=True` when that window already existed before the
    launch (hidden, minimised, cloaked or simply open): it can hold the user's own
    documents (Windows 11 Notepad keeps a hidden window with every open tab and shows it
    again), so typing into it can overwrite the user's work."""
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    kw = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    ids_before = _all_window_ids()
    try:
        subprocess.Popen(command, **kw)
    except OSError:
        subprocess.Popen(f'cmd /c start "" {command}', **kw)
    first = shlex.split(command, posix=False)[0].strip('"') if command.strip() else ""
    exe = os.path.splitext(os.path.basename(first))[0].lower()
    fg_before = _foreground()
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        wins = list_windows()
        new = [w for w in wins if w["id"] not in before]
        found = new[0] if new else None
        fg = _foreground()
        if not found and fg and fg != fg_before and time.monotonic() - start > 1.0:
            w = next((w for w in wins if w["id"] == _root(fg)), None)
            if w and exe and exe in os.path.splitext(w["wm_class"])[0].lower():
                found = w
        if found:
            found["reused"] = found["id"] in ids_before
            return found
        time.sleep(0.3)
    raise TimeoutError(f"no new window appeared within {timeout:.0f}s after launching {command!r}. If the app "
                       f"was already running, use `focus` instead; check names with `windows`.")


def format_windows(wins: list[dict]) -> str:
    return "\n".join(f"{'*' if w['active'] else ' '} {w['id']:>10}  {w['wm_class'][:30]:<30} {w['title']}"
                     for w in wins) or "no windows"
