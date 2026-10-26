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
  * registry "Scancode Map" overrides rewrite hardware scancodes inside the keyboard
    driver; injected input never passes through them, so they need no correction.

Set AUTOMONKEY_TYPING=keys (or pass mode="keys") to type text as real key presses
instead, for targets that ignore Unicode injection (some games, remote desktops, VMs).
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


def _mode(mode: str | None) -> str:
    return (mode or os.environ.get("AUTOMONKEY_TYPING") or "unicode").lower()


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
    MAPVK_VK_TO_VSC_EX = 4
    VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12

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

    # Named keys ('enter', 'ctrl', 'f5', ...) have fixed virtual-key codes.
    _NAMED = {k: v for k, v in pyautogui.platformModule.keyboardMapping.items() if len(k) > 1 and v}

    def foreground_layout() -> int:
        """Keyboard layout (HKL) of the window that will receive the input."""
        hwnd = _u32.GetForegroundWindow()
        tid = _u32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0
        return _u32.GetKeyboardLayout(tid)

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

    def _key(vk: int, up: bool, hkl, remaps) -> _INPUT:
        vk = _source_vk(vk, remaps)
        scan = _u32.MapVirtualKeyExW(vk, MAPVK_VK_TO_VSC_EX, hkl)
        flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if scan >> 8 == 0xE0 else 0)
        return _INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=_KEYBDINPUT(wVk=vk, wScan=scan & 0xFF, dwFlags=flags)))

    def _chord(vks: list[int], hkl, remaps) -> list[_INPUT]:
        return [_key(vk, False, hkl, remaps) for vk in vks] + [_key(vk, True, hkl, remaps) for vk in reversed(vks)]

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
        hkl = foreground_layout()
        remaps = _remaps()
        as_keys = _mode(mode) == "keys"
        for ch in text.replace("\r\n", "\n").replace("\r", "\n"):
            pyautogui.failSafeCheck()
            vks = [_NAMED[_TEXT_KEYS[ch]]] if ch in _TEXT_KEYS else char_keys(ch, hkl) if as_keys else None
            _send(_chord(vks, hkl, remaps) if vks else _unicode(ch))
            time.sleep(interval)
        time.sleep(pyautogui.PAUSE)

    def press(keys, presses: int = 1, interval: float = 0.0):
        """Press and release each key in turn: a named key ('enter', 'f5') or a character."""
        hkl = foreground_layout()
        remaps = _remaps()
        for _ in range(presses):
            for key in [keys] if isinstance(keys, str) else keys:
                pyautogui.failSafeCheck()
                key = _name(key)
                if key in _NAMED:
                    _send(_chord([_NAMED[key]], hkl, remaps))
                elif len(key) == 1:
                    vks = char_keys(key, hkl)
                    _send(_chord(vks, hkl, remaps) if vks else _unicode(key))
                else:
                    raise ValueError(f"unknown key {key!r}")
                time.sleep(interval)
        time.sleep(pyautogui.PAUSE)

    def hotkey(*keys, interval: float = 0.0):
        """Hold the keys down in order, then release them in reverse: hotkey('ctrl', 'z')."""
        pyautogui.failSafeCheck()
        hkl = foreground_layout()
        remaps = _remaps()
        vks = _shortcut_vks([_name(k) for k in _flatten(keys)], hkl)
        if interval:
            for inp in _chord(vks, hkl, remaps):
                _send([inp])
                time.sleep(interval)
        else:
            _send(_chord(vks, hkl, remaps))
        time.sleep(pyautogui.PAUSE)

else:
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
