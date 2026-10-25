"""Mouse input that every application actually receives.

pyautogui moves the cursor with SetCursorPos on Windows. That call repositions the
cursor but never enters the input stack: no WM_MOUSEMOVE / pointer event is produced,
so WinUI/UWP/XAML apps (Windows 11 Paint, Notepad, Settings), canvas widgets and
drag-and-drop see only the press and the release - a drag becomes a click, a stroke
becomes a dot (see ai_tips.md section 1).

On Windows this module injects everything with SendInput instead: absolute moves over
the whole virtual desktop (every monitor), buttons and the wheel, and it glides
through dense intermediate points (~2 px apart, ~125 events/s, like a human hand).
Elsewhere it falls back to pyautogui, which already produces real events on X11.

All coordinates are *input pixels*: physical screen pixels of the virtual desktop on
Windows (the process is made DPI aware), pyautogui pixels elsewhere.
"""
from __future__ import annotations

import math
import sys
import time

import pyautogui

STEP_PX = 2.0      # distance between injected move events
STEP_DT = 0.008    # seconds between injected move events (~125 events/s)
CORNER = 2         # fail-safe: the user pushed the mouse into a screen corner

_BUTTONS = ("left", "right", "middle")


def _check_button(button: str) -> str:
    b = (button or "left").lower()
    if b not in _BUTTONS:
        raise ValueError(f"unknown mouse button {button!r} (use left, right or middle)")
    return b


def densify(points: list[tuple[float, float]], step: float = STEP_PX) -> list[tuple[int, int]]:
    """Every point of the polyline `points`, at most `step` pixels apart (endpoints kept)."""
    if not points:
        return []
    out = [(round(points[0][0]), round(points[0][1]))]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        n = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / step))
        for i in range(1, n + 1):
            p = (round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n))
            if p != out[-1]:
                out.append(p)
    return out


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.WinDLL("user32", use_last_error=True)

    INPUT_MOUSE = 0
    MOVE, ABSOLUTE, VIRTUALDESK = 0x0001, 0x8000, 0x4000
    WHEEL, HWHEEL = 0x0800, 0x1000
    _DOWN = {"left": 0x0002, "right": 0x0008, "middle": 0x0020}
    _UP = {"left": 0x0004, "right": 0x0010, "middle": 0x0040}
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
    SM_SWAPBUTTON = 23

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _INPUTUNION(ctypes.Union):  # sized by its largest member, as SendInput expects
        _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _u32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    _u32.SendInput.restype = wintypes.UINT

    def _mouse(flags: int, dx: int = 0, dy: int = 0, data: int = 0):
        inp = _INPUT(type=INPUT_MOUSE)
        inp.u.mi = _MOUSEINPUT(dx, dy, ctypes.c_uint32(data).value, flags, 0, 0)
        if _u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT)) != 1:
            err = ctypes.get_last_error()
            raise OSError(f"SendInput was blocked (error {err}): the target window may belong to an "
                          "elevated (administrator) process, or the desktop is locked")

    def virtual_screen() -> tuple[int, int, int, int]:
        """(left, top, width, height) of the virtual desktop, all monitors."""
        g = _u32.GetSystemMetrics
        return (g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN), g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN))

    def position() -> tuple[int, int]:
        pt = wintypes.POINT()
        _u32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _failsafe():
        if not pyautogui.FAILSAFE:
            return
        x, y = position()
        vx, vy, vw, vh = virtual_screen()
        if (x - vx <= CORNER or vx + vw - 1 - x <= CORNER) and (y - vy <= CORNER or vy + vh - 1 - y <= CORNER):
            raise pyautogui.FailSafeException("mouse moved to a screen corner: AutoMonkey stopped (fail-safe)")

    def _raw_move(x: int, y: int):
        vx, vy, vw, vh = virtual_screen()
        nx = round((x - vx) * 65535 / max(vw - 1, 1))
        ny = round((y - vy) * 65535 / max(vh - 1, 1))
        _mouse(MOVE | ABSOLUTE | VIRTUALDESK, nx, ny)

    def _physical(button: str) -> str:
        # SendInput's LEFTDOWN is the *physical* left button; honour swapped buttons.
        if _u32.GetSystemMetrics(SM_SWAPBUTTON) and button in ("left", "right"):
            return "right" if button == "left" else "left"
        return button

    def button_down(button: str = "left"):
        _mouse(_DOWN[_physical(_check_button(button))])

    def button_up(button: str = "left"):
        _mouse(_UP[_physical(_check_button(button))])

    def _wheel(clicks: int, horizontal: bool = False):
        _mouse(HWHEEL if horizontal else WHEEL, data=int(clicks) * 120)

else:
    def virtual_screen() -> tuple[int, int, int, int]:
        w, h = pyautogui.size()
        return 0, 0, w, h

    def position() -> tuple[int, int]:
        p = pyautogui.position()
        return int(p[0]), int(p[1])

    def _failsafe():
        pyautogui.failSafeCheck()

    def _raw_move(x: int, y: int):
        pyautogui.moveTo(x, y, _pause=False)

    def button_down(button: str = "left"):
        pyautogui.mouseDown(button=_check_button(button), _pause=False)

    def button_up(button: str = "left"):
        pyautogui.mouseUp(button=_check_button(button), _pause=False)

    def _wheel(clicks: int, horizontal: bool = False):
        (pyautogui.hscroll if horizontal else pyautogui.scroll)(int(clicks), _pause=False)


# Buttons this process holds down, so a failed script never leaves one stuck.
held: set[str] = set()


def press(button: str = "left"):
    _failsafe()
    button_down(button)
    held.add(_check_button(button))


def release(button: str = "left"):
    button_up(button)
    held.discard(_check_button(button))


def release_all():
    for b in list(held):
        try:
            release(b)
        except Exception:
            pass


def glide(points: list[tuple[float, float]], step: float = STEP_PX, dt: float = STEP_DT):
    """Move through every point of the polyline as a stream of real move events."""
    pts = densify(points, step)
    for i, (x, y) in enumerate(pts):
        if i % 25 == 0:
            _failsafe()
        _raw_move(x, y)
        if dt:
            time.sleep(dt)


def move_to(x: float, y: float, glide_from_current: bool = True):
    """Move the pointer like a hand would: a short dense glide from where it is now, so
    hover effects, tooltips and enter/leave events fire."""
    _failsafe()
    if glide_from_current:
        sx, sy = position()
        dist = math.hypot(x - sx, y - sy)
        # Long jumps: a few coarse steps are enough for hover tracking, and stay fast.
        step = max(STEP_PX, dist / 40)
        glide([(sx, sy), (x, y)], step=step, dt=0.004)
    else:
        _raw_move(round(x), round(y))


def click(x: float, y: float, button: str = "left", clicks: int = 1, interval: float = 0.06):
    move_to(x, y)
    time.sleep(0.03)
    for i in range(max(1, int(clicks))):
        press(button)
        time.sleep(0.02)
        release(button)
        if i + 1 < clicks:
            time.sleep(interval)


def drag(points: list[tuple[float, float]], button: str = "left", hold: float = 0.15):
    """Press at the first point, glide through the others, release at the last one.
    Pauses after the press and before the release so drag-and-drop sources and
    targets (which wait for a hover) recognise the gesture."""
    if len(points) < 2:
        raise ValueError("a drag needs at least two points")
    move_to(*points[0])
    time.sleep(0.05)
    press(button)
    try:
        time.sleep(hold)
        # Nudge past the system drag threshold (4 px) before the real path starts.
        x0, y0 = points[0]
        glide([(x0, y0), (x0 + 3, y0), (x0, y0)], step=1)
        glide(points)
        time.sleep(hold)
    finally:
        release(button)


def scroll(clicks: int, x: float | None = None, y: float | None = None, horizontal: bool = False):
    """Wheel notches: positive scrolls up (or right when horizontal)."""
    if x is not None and y is not None:
        move_to(x, y)
    _failsafe()
    _wheel(clicks, horizontal)
