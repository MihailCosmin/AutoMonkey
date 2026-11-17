"""Keyboard-layout-aware typing, key presses and shortcuts.

pyautogui maps characters to keys with the layout of the *Python* thread (fixed at
import time) and sends bare virtual-key codes, which key remappers then rewrite. On
Windows that mangles text whenever the target window uses another layout (German
QWERTZ: ';' arrives as 'ö') or a remapper swaps keys (PowerToys y<->z: 'KEYBOARD'
arrives as 'KEZBOARD').

On Windows:
  * text is injected as Unicode characters (KEYEVENTF_UNICODE): independent of the
    layout and of key remappers, and it covers non-ASCII text (ă, ß, €) as well;
  * keys and shortcuts are resolved with the layout of the *foreground* window, and
    PowerToys Keyboard Manager single-key remaps are undone, so the app receives the
    key that was asked for (ctrl+z stays undo when y and z are swapped);
  * every key carries its scan code, with the extended flag of the arrows, Home/End,
    PgUp/PgDn, Insert/Delete, right Ctrl/Alt and numpad '/' (MapVirtualKeyEx leaves it
    off the navigation keys, which then read as numpad keys);
  * registry "Scancode Map" overrides rewrite hardware scancodes inside the keyboard
    driver; injected input never passes through them, so they need no correction.

Remote desktops. The RDP client (mstsc, the Remote Desktop app) forwards scan codes to
the remote session: a key without its extended flag arrives there as a numpad key ('4'
instead of Left while Num Lock is on), and it takes the keys before PowerToys does, so
undoing a remap would swap y and z there. When the foreground window belongs to it, keys
and shortcuts are sent as scan codes only (KEYEVENTF_SCANCODE without a virtual key, like
a hardware keyboard) and remaps are left alone; text stays Unicode, which arrives
unchanged whatever the remote keyboard layout. AUTOMONKEY_KEYS=scancode sends scan codes
to every window (other remote viewers, VMs), AUTOMONKEY_KEYS=vk never; the default is auto.

A call stops with FocusChanged when another program takes the foreground while it
types (the user clicked elsewhere), so the rest of the text never lands there.

Set AUTOMONKEY_TYPING=keys (or pass mode="keys") to type text as real key presses
instead, for targets that ignore Unicode injection (some games, VMs).
Elsewhere this falls back to pyautogui, pasting text it cannot type.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

import pyautogui

_TEXT_KEYS = {"\n": "enter", "\t": "tab"}

KEY_STYLES = ("auto", "scancode", "vk")
# The RDP client's windows: a session (TscShellContainerClass) and RemoteApp windows
# (RAIL_WINDOW), in Remote Desktop Connection (mstsc.exe) or the Remote Desktop app /
# Windows App (msrdc.exe).
REMOTE_DESKTOP_CLASSES = frozenset({"TscShellContainerClass", "RAIL_WINDOW"})
REMOTE_DESKTOP_EXES = frozenset({"mstsc.exe", "msrdc.exe"})


class FocusChanged(RuntimeError):
    """Another program took the foreground while keys were being sent to a window."""


def _mode(mode: str | None) -> str:
    return (mode or os.environ.get("AUTOMONKEY_TYPING") or "unicode").lower()


def key_style() -> str:
    """How keys are sent: 'auto' (scan codes into remote desktops), 'scancode' or 'vk'
    (AUTOMONKEY_KEYS)."""
    style = (os.environ.get("AUTOMONKEY_KEYS") or "auto").strip().lower()
    if style not in KEY_STYLES:
        raise ValueError(f"AUTOMONKEY_KEYS={style!r}: use auto, scancode or vk")
    return style


def is_remote_desktop(class_name: str, exe: str) -> bool:
    """True for a window of the RDP client, which forwards scan codes to a remote session."""
    return class_name in REMOTE_DESKTOP_CLASSES or exe.lower() in REMOTE_DESKTOP_EXES


def _flatten(keys) -> list[str]:
    if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
        keys = keys[0]
    return [str(k) for k in keys]


def _name(key: str) -> str:
    return key if len(key) == 1 else key.lower()


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x1
    KEYEVENTF_KEYUP = 0x2
    KEYEVENTF_UNICODE = 0x4
    KEYEVENTF_SCANCODE = 0x8
    MAPVK_VK_TO_VSC_EX = 4
    VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

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

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    _u32.GetForegroundWindow.restype = wintypes.HWND
    _u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    _u32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _u32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _u32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _u32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
    _u32.GetKeyboardLayout.restype = wintypes.HKL
    _u32.VkKeyScanExW.argtypes = (wintypes.WCHAR, wintypes.HKL)
    _u32.VkKeyScanExW.restype = ctypes.c_short
    _u32.MapVirtualKeyExW.argtypes = (wintypes.UINT, wintypes.UINT, wintypes.HKL)
    _u32.MapVirtualKeyExW.restype = wintypes.UINT
    _u32.ToUnicodeEx.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
                                 wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL)
    _u32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    _u32.SendInput.restype = wintypes.UINT
    _k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W))
    _k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W))
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD))

    # Named keys ('enter', 'ctrl', 'f5', ...) have fixed virtual-key codes.
    _NAMED = {k: v for k, v in pyautogui.platformModule.keyboardMapping.items() if len(k) > 1 and v}

    # Scan codes (0xE0xx: extended key) MapVirtualKeyEx(MAPVK_VK_TO_VSC_EX) does not give
    # reliably: on Windows 11 it returns the arrows, Home/End, PgUp/PgDn, Insert and Delete
    # without the 0xE0 prefix (VK_DOWN -> 0x50, numpad 2) and Print Screen as 0x54 (Alt+SysRq).
    _EXTENDED_SCAN = {
        0x21: 0xE049, 0x22: 0xE051, 0x23: 0xE04F, 0x24: 0xE047,  # PgUp, PgDn, End, Home
        0x25: 0xE04B, 0x26: 0xE048, 0x27: 0xE04D, 0x28: 0xE050,  # Left, Up, Right, Down
        0x2C: 0xE037, 0x2D: 0xE052, 0x2E: 0xE053,                # Print Screen, Insert, Delete
        0x5B: 0xE05B, 0x5C: 0xE05C, 0x5D: 0xE05D,                # left/right Windows, Menu
        0x6F: 0xE035, 0x90: 0xE045,                              # numpad '/', Num Lock
        0xA3: 0xE01D, 0xA5: 0xE038,                              # right Ctrl, right Alt (AltGr)
    }

    def vk_scan(vk: int, hkl) -> int:
        """Set-1 scan code of virtual key `vk` on layout `hkl` (0xE0xx: extended key)."""
        return _EXTENDED_SCAN.get(vk) or _u32.MapVirtualKeyExW(vk, MAPVK_VK_TO_VSC_EX, hkl)

    def _foreground() -> int:
        return int(_u32.GetForegroundWindow() or 0)

    def _thread_pid(hwnd: int) -> tuple[int, int]:
        pid = wintypes.DWORD()
        tid = _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return tid, pid.value

    def _class_name(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        _u32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    def _title(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        _u32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    _exe_cache: dict[int, str] = {}

    def _exe(pid: int) -> str:
        """File name of a process' executable ('' if it can't be read)."""
        if pid not in _exe_cache:
            name = ""
            h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid) if pid else None
            if h:
                try:
                    size = wintypes.DWORD(1024)
                    buf = ctypes.create_unicode_buffer(size.value)
                    if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                        name = os.path.basename(buf.value)
                finally:
                    _k32.CloseHandle(h)
            if len(_exe_cache) > 512:
                _exe_cache.clear()
            _exe_cache[pid] = name
        return _exe_cache[pid]

    def remote_desktop_window(hwnd: int | None = None) -> bool:
        """True if `hwnd` (default: the foreground window) belongs to the RDP client."""
        hwnd = _foreground() if hwnd is None else hwnd
        return bool(hwnd) and is_remote_desktop(_class_name(hwnd), _exe(_thread_pid(hwnd)[1]))

    def uses_scancodes() -> bool:
        """True if keys sent now go out as scan codes (AUTOMONKEY_KEYS, remote desktop in front)."""
        style = key_style()
        return style == "scancode" or (style == "auto" and remote_desktop_window())

    def foreground_layout() -> int:
        """Keyboard layout (HKL) of the window that will receive the input."""
        hwnd = _foreground()
        return _u32.GetKeyboardLayout(_thread_pid(hwnd)[0] if hwnd else 0)

    def _running(exe: str) -> bool:
        snap = _k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if snap in (None, wintypes.HANDLE(-1).value):
            return False
        try:
            entry = _PROCESSENTRY32W(dwSize=ctypes.sizeof(_PROCESSENTRY32W))
            ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower() == exe:
                    return True
                ok = _k32.Process32NextW(snap, ctypes.byref(entry))
            return False
        finally:
            _k32.CloseHandle(snap)

    def powertoys_remaps(root: str | None = None) -> dict[int, int]:
        """Single-key remaps PowerToys Keyboard Manager applies, {original_vk: new_vk}.
        Its hook rewrites injected keys too, so these have to be undone. Empty when the
        engine isn't running."""
        root = root or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "PowerToys", "Keyboard Manager")
        try:
            with open(os.path.join(root, "settings.json"), encoding="utf-8-sig") as f:
                config = json.load(f)["properties"]["activeConfiguration"]["value"]
            with open(os.path.join(root, f"{config}.json"), encoding="utf-8-sig") as f:
                entries = json.load(f)["remapKeys"]["inProcess"]
        except (OSError, ValueError, KeyError, TypeError):
            return {}
        remaps = {}
        for e in entries:
            new = str(e.get("newRemapKeys", ""))
            if new.isdigit():  # "17;67" would be a key -> shortcut remap; leave those alone
                remaps[int(e["originalKeys"])] = int(new)
        return remaps

    _remap_cache = (0.0, {})

    def _remaps() -> dict[int, int]:
        global _remap_cache
        stamp, cached = _remap_cache
        if time.monotonic() - stamp > 5:
            cached = powertoys_remaps() if _running("powertoys.keyboardmanagerengine.exe") else {}
            _remap_cache = (time.monotonic(), cached)
        return cached

    def _source_vk(vk: int, remaps: dict[int, int]) -> int:
        """The key to inject so that, after remapping, the app receives `vk`."""
        for orig, new in remaps.items():
            if new == vk:
                return orig
        return vk

    def _key_name(vk: int) -> str:
        names = [k for k, v in _NAMED.items() if v == vk]
        return repr(names[0]) if names else f"0x{vk:02X}"

    def _key(vk: int, up: bool, hkl, remaps, scancode: bool = False) -> _INPUT:
        """One key event. scancode=True: the scan code alone, as the RDP client needs it."""
        if not scancode:
            vk = _source_vk(vk, remaps)
        scan = vk_scan(vk, hkl)
        flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if scan >> 8 == 0xE0 else 0)
        if not scancode:
            return _INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=_KEYBDINPUT(wVk=vk, wScan=scan & 0xFF, dwFlags=flags)))
        if not scan & 0xFF or scan >> 8 not in (0, 0xE0):
            raise ValueError(f"key {_key_name(vk)} has no scan code, so it can't be sent to a remote desktop "
                             "(AUTOMONKEY_KEYS=vk sends it as a virtual key)")
        return _INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=_KEYBDINPUT(
            wVk=0, wScan=scan & 0xFF, dwFlags=flags | KEYEVENTF_SCANCODE)))

    def _chord(vks: list[int], hkl, remaps, scancode: bool = False) -> list[_INPUT]:
        return ([_key(vk, False, hkl, remaps, scancode) for vk in vks]
                + [_key(vk, True, hkl, remaps, scancode) for vk in reversed(vks)])

    def _unicode(ch: str) -> list[_INPUT]:
        data = ch.encode("utf-16-le")  # characters beyond the BMP are two surrogate units
        out = []
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                out.append(_INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=_KEYBDINPUT(wScan=unit, dwFlags=flags))))
        return out

    def _send(inputs: list[_INPUT]):
        arr = (_INPUT * len(inputs))(*inputs)
        if _u32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT)) != len(inputs):
            raise OSError(f"SendInput failed: {ctypes.WinError(ctypes.get_last_error())}")

    class _Target:
        """The window one call types into: its layout, how its keys must be sent, and a
        check that it is still in front."""

        def __init__(self):
            self.hwnd = _foreground()
            tid, self.pid = _thread_pid(self.hwnd) if self.hwnd else (0, 0)
            self.hkl = _u32.GetKeyboardLayout(tid)
            style = key_style()
            self.scancode = style == "scancode" or (style == "auto" and remote_desktop_window(self.hwnd))
            self.remaps = {} if self.scancode else _remaps()

        def chord(self, vks: list[int]) -> list[_INPUT]:
            return _chord(vks, self.hkl, self.remaps, self.scancode)

        def keys(self, vks: list[int], up: bool) -> list[_INPUT]:
            return [_key(vk, up, self.hkl, self.remaps, self.scancode) for vk in vks]

        def check(self):
            """Raise FocusChanged if another program has taken the foreground since the
            call started (its own dialogs are fine)."""
            if not self.pid:  # nothing was in front at the start: nothing to compare with
                return
            fg = _foreground()
            deadline = time.monotonic() + 0.5
            while not fg and time.monotonic() < deadline:  # between two windows
                time.sleep(0.02)
                fg = _foreground()
            if fg == self.hwnd or (fg and _thread_pid(fg)[1] == self.pid):
                return
            now = f"{_title(fg)!r} ({_exe(_thread_pid(fg)[1]) or 'unknown program'})" if fg else "no window"
            raise FocusChanged(f"keyboard input stopped: the active window changed from {_title(self.hwnd)!r} "
                               f"to {now} while keys were being sent (a click elsewhere?); the remaining "
                               "keys were not sent")

        def send(self, inputs: list[_INPUT], check: bool = True):
            if check:
                self.check()
            _send(inputs)

    def char_keys(ch: str, hkl) -> list[int] | None:
        """[modifier VKs..., VK] that type `ch` on layout `hkl`, or None if the layout
        has no plain key for it (missing, or only reachable through a dead key)."""
        if ord(ch) > 0xFFFF:  # no layout has a key for a surrogate pair
            return None
        res = _u32.VkKeyScanExW(ch, hkl)
        if res == -1:
            return None
        vk, state = res & 0xFF, (res >> 8) & 0xFF
        if state & ~0x7:  # Hankaku / layout-specific shift states we can't press
            return None
        mods = [m for bit, m in ((1, VK_SHIFT), (2, VK_CONTROL), (4, VK_MENU)) if state & bit]
        keystate = (ctypes.c_ubyte * 256)()
        for m in mods:
            keystate[m] = 0x80
        buf = ctypes.create_unicode_buffer(8)
        # flag 0x4: don't touch the thread's dead-key state (Windows 10 1607+)
        if _u32.ToUnicodeEx(vk, _u32.MapVirtualKeyExW(vk, 0, hkl), keystate, buf, 8, 0x4, hkl) < 0:
            return None
        return mods + [vk]

    def _shortcut_vks(keys: list[str], hkl) -> list[int]:
        vks = []
        for key in keys:
            if key in _NAMED:
                add = [_NAMED[key]]
            elif len(key) == 1 and key.isascii() and key.isalnum():
                add = [ord(key.upper())]  # apps match letter/digit shortcuts by VK on every layout
            else:  # punctuation: whatever key (and shift) types it on this layout
                add = char_keys(key, hkl) if len(key) == 1 else None
                if not add:
                    raise ValueError(f"key {key!r} is unknown or not on the active keyboard layout")
            vks += [vk for vk in add if vk not in vks]
        return vks

    def write(text: str, interval: float = 0.01, mode: str | None = None):
        """Type `text` exactly, whatever the keyboard layout or key remaps."""
        t = _Target()
        as_keys = _mode(mode) == "keys"
        for ch in text.replace("\r\n", "\n").replace("\r", "\n"):
            pyautogui.failSafeCheck()
            vks = [_NAMED[_TEXT_KEYS[ch]]] if ch in _TEXT_KEYS else char_keys(ch, t.hkl) if as_keys else None
            t.send(t.chord(vks) if vks else _unicode(ch))
            time.sleep(interval)
        time.sleep(pyautogui.PAUSE)

    def press(keys, presses: int = 1, interval: float = 0.0):
        """Press and release each key in turn: a named key ('enter', 'f5') or a character."""
        t = _Target()
        for _ in range(presses):
            for key in [keys] if isinstance(keys, str) else keys:
                pyautogui.failSafeCheck()
                key = _name(key)
                if key in _NAMED:
                    t.send(t.chord([_NAMED[key]]))
                elif len(key) == 1:
                    vks = char_keys(key, t.hkl)
                    t.send(t.chord(vks) if vks else _unicode(key))
                else:
                    raise ValueError(f"unknown key {key!r}")
                time.sleep(interval)
        time.sleep(pyautogui.PAUSE)

    def hotkey(*keys, interval: float = 0.0):
        """Hold the keys down in order, then release them in reverse: hotkey('ctrl', 'z')."""
        pyautogui.failSafeCheck()
        t = _Target()
        events = t.chord(_shortcut_vks([_name(k) for k in _flatten(keys)], t.hkl))
        t.check()
        if interval:
            for inp in events:  # no focus check in between: a half-sent chord would leave keys held
                _send([inp])
                time.sleep(interval)
        else:
            _send(events)
        time.sleep(pyautogui.PAUSE)

    def key_down(key: str):
        """Hold a key down until key_up (keydown ctrl; click ...; keyup ctrl). A character
        holds the keys that type it, shift included."""
        pyautogui.failSafeCheck()
        t = _Target()
        t.send(t.keys(_shortcut_vks([_name(key)], t.hkl), up=False))

    def key_up(key: str):
        """Release a key held with key_down; sent whichever window is in front now."""
        t = _Target()
        t.send(t.keys(list(reversed(_shortcut_vks([_name(key)], t.hkl))), up=True), check=False)

else:
    def remote_desktop_window(hwnd: int | None = None) -> bool:
        return False

    def uses_scancodes() -> bool:
        return False

    def write(text: str, interval: float = 0.01, mode: str | None = None):
        """Type `text`; pyautogui can't type non-ASCII (e.g. ă, ș), so that is pasted."""
        if shutil.which("xdotool") and os.environ.get("DISPLAY"):
            # pyautogui sends US-layout key codes: '/' comes out as '7' on a German layout; xdotool follows the layout
            subprocess.run(["xdotool", "type", "--delay", str(max(int(interval * 1000), 1)), "--", text], check=True)
        elif text.isascii():
            pyautogui.write(text, interval=interval)
        else:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")

    def press(keys, presses: int = 1, interval: float = 0.0):
        pyautogui.press([_name(k) for k in ([keys] if isinstance(keys, str) else keys)],
                        presses=presses, interval=interval)

    def hotkey(*keys, interval: float = 0.0):
        pyautogui.hotkey(*[_name(k) for k in _flatten(keys)], interval=interval)

    def key_down(key: str):
        pyautogui.keyDown(_name(key), _pause=False)

    def key_up(key: str):
        pyautogui.keyUp(_name(key), _pause=False)
