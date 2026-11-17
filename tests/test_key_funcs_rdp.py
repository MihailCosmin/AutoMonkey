"""Key events for remote desktops (RAM_Commander_Automations-N3), the focus guard, wheel
notches and the region screen grab. Nothing here sends real input: SendInput and
mouse_event are replaced by recorders, the foreground window by a fake one. Only the
screen-grab test reads the real screen."""
import sys

import pytest

pytest.importorskip("pyautogui")

if sys.platform != "win32":
    pytest.skip("Windows key events, wheel and GDI grab", allow_module_level=True)

import ctypes

import numpy as np

from automonkey import key_funcs as kf
from automonkey import mouse_funcs, utils

KEYUP, UNICODE, SCANCODE, EXT = 0x2, 0x4, 0x8, 0x1
VK_LEFT, VK_DOWN, VK_DELETE, VK_SNAPSHOT, VK_RETURN, VK_PAUSE = 0x25, 0x28, 0x2E, 0x2C, 0x0D, 0x13
MSTSC, OTHER = 1001, 2002          # fake window handles
MSTSC_PID, OTHER_PID = 501, 902


@pytest.fixture(scope="module")
def german():
    return ctypes.windll.user32.LoadKeyboardLayoutW("00000407", 0)  # load, don't activate


def _events(inputs):
    return [(i.u.ki.wVk, i.u.ki.wScan, i.u.ki.dwFlags) for i in inputs]


# --- scan codes ---------------------------------------------------------------

def test_vk_scan_sets_the_extended_prefix(german):
    # MapVirtualKeyEx gives the navigation keys without 0xE0 on Windows 11: Left would be numpad 4
    assert kf.vk_scan(VK_LEFT, german) == 0xE04B
    assert kf.vk_scan(VK_DOWN, german) == 0xE050
    assert kf.vk_scan(VK_DELETE, german) == 0xE053
    assert kf.vk_scan(VK_SNAPSHOT, german) == 0xE037
    assert kf.vk_scan(VK_RETURN, german) == 0x1C
    assert kf.vk_scan(ord("Z"), german) == 0x15  # QWERTZ: Z sits where US has Y
    assert kf.vk_scan(ord("Y"), german) == 0x2C


def test_vk_events_carry_the_extended_flag(german):
    assert _events([kf._key(VK_LEFT, False, german, {})]) == [(VK_LEFT, 0x4B, EXT)]


def test_scancode_events_have_no_virtual_key(german):
    assert _events([kf._key(VK_LEFT, True, german, {}, scancode=True)]) == [(0, 0x4B, EXT | KEYUP | SCANCODE)]
    assert _events([kf._key(VK_RETURN, False, german, {}, scancode=True)]) == [(0, 0x1C, SCANCODE)]


def test_scancode_events_leave_powertoys_remaps_alone(german):
    swap = {ord("Z"): ord("Y"), ord("Y"): ord("Z")}  # PowerToys y<->z
    # locally the remap is undone (inject Y so the app gets Z) ...
    assert _events([kf._key(ord("Z"), False, german, swap)]) == [(ord("Y"), 0x2C, 0)]
    # ... but the RDP client takes the keys before PowerToys: send Z's own scan code
    assert _events([kf._key(ord("Z"), False, german, swap, scancode=True)]) == [(0, 0x15, SCANCODE)]


def test_scancode_rejects_keys_without_one(german):
    with pytest.raises(ValueError, match="'pause'.*no scan code"):
        kf._key(VK_PAUSE, False, german, {}, scancode=True)


def test_is_remote_desktop():
    assert kf.is_remote_desktop("TscShellContainerClass", "mstsc.exe")
    assert kf.is_remote_desktop("RAIL_WINDOW", "")
    assert kf.is_remote_desktop("SomethingElse", "MSRDC.EXE")
    assert not kf.is_remote_desktop("Notepad", "notepad.exe")
    assert not kf.is_remote_desktop("RustdeskMultiWindow", "rustdesk.exe")


def test_key_style(monkeypatch):
    monkeypatch.delenv("AUTOMONKEY_KEYS", raising=False)
    assert kf.key_style() == "auto"
    monkeypatch.setenv("AUTOMONKEY_KEYS", " ScanCode ")
    assert kf.key_style() == "scancode"
    monkeypatch.setenv("AUTOMONKEY_KEYS", "rdp")
    with pytest.raises(ValueError, match="auto, scancode or vk"):
        kf.key_style()


# --- write / press / hotkey against a fake foreground window --------------------

class Desktop:
    """A fake foreground window plus a recorder for SendInput."""

    def __init__(self, monkeypatch, german):
        self.fg = MSTSC
        self.sent = []
        self.after_send = None  # called after each SendInput: lets a test move the focus
        windows = {MSTSC: ("TscShellContainerClass", MSTSC_PID, "10.3.1.138 - Remote Desktop Connection"),
                   OTHER: ("Chrome_WidgetWin_1", OTHER_PID, "Claude Workbench"),
                   MSTSC + 1: ("BBarWindowClass", MSTSC_PID, "BBar")}
        exes = {MSTSC_PID: "mstsc.exe", OTHER_PID: "workbench.exe"}
        monkeypatch.setattr(kf, "_foreground", lambda: self.fg)
        monkeypatch.setattr(kf, "_thread_pid", lambda hwnd: (7, windows[hwnd][1]) if hwnd else (0, 0))
        monkeypatch.setattr(kf, "_class_name", lambda hwnd: windows[hwnd][0])
        monkeypatch.setattr(kf, "_title", lambda hwnd: windows[hwnd][2] if hwnd else "")
        monkeypatch.setattr(kf, "_exe", lambda pid: exes.get(pid, ""))
        monkeypatch.setattr(kf._u32, "GetKeyboardLayout", lambda tid: german)
        monkeypatch.setattr(kf, "_remaps", lambda: {ord("Z"): ord("Y"), ord("Y"): ord("Z")})
        monkeypatch.setattr(kf.pyautogui, "failSafeCheck", lambda: None)
        monkeypatch.setattr(kf.pyautogui, "PAUSE", 0)
        monkeypatch.delenv("AUTOMONKEY_KEYS", raising=False)
        monkeypatch.setattr(kf, "_send", self.send)

    def send(self, inputs):
        self.sent += _events(inputs)
        if self.after_send:
            self.after_send()


@pytest.fixture
def desk(monkeypatch, german):
    return Desktop(monkeypatch, german)


def test_mstsc_in_front_means_scan_codes(desk):
    assert kf.uses_scancodes()
    desk.fg = OTHER
    assert not kf.uses_scancodes()


def test_write_into_a_remote_desktop(desk):
    kf.write("ä\n", interval=0)
    assert desk.sent == [(0, ord("ä"), UNICODE), (0, ord("ä"), UNICODE | KEYUP),  # text: Unicode
                         (0, 0x1C, SCANCODE), (0, 0x1C, SCANCODE | KEYUP)]        # newline: Enter key


def test_press_and_hotkey_into_a_remote_desktop(desk):
    kf.press(["down", "z"])
    kf.hotkey("ctrl", "z")
    assert desk.sent == [(0, 0x50, SCANCODE | EXT), (0, 0x50, SCANCODE | EXT | KEYUP),
                         (0, 0x15, SCANCODE), (0, 0x15, SCANCODE | KEYUP),
                         (0, 0x1D, SCANCODE), (0, 0x15, SCANCODE), (0, 0x15, SCANCODE | KEYUP),
                         (0, 0x1D, SCANCODE | KEYUP)]


def test_altgr_character_as_scan_codes(desk):
    kf.press("@")  # German: AltGr+Q = Ctrl+Alt+Q
    assert desk.sent == [(0, 0x1D, SCANCODE), (0, 0x38, SCANCODE), (0, 0x10, SCANCODE),
                         (0, 0x10, SCANCODE | KEYUP), (0, 0x38, SCANCODE | KEYUP), (0, 0x1D, SCANCODE | KEYUP)]


def test_local_window_keeps_virtual_keys_and_remaps(desk):
    desk.fg = OTHER
    kf.press(["down", "z"])
    assert desk.sent == [(VK_DOWN, 0x50, EXT), (VK_DOWN, 0x50, EXT | KEYUP),
                         (ord("Y"), 0x2C, 0), (ord("Y"), 0x2C, KEYUP)]  # PowerToys turns it into Z


def test_key_style_forces_either_way(desk, monkeypatch):
    monkeypatch.setenv("AUTOMONKEY_KEYS", "vk")
    kf.press("left")
    monkeypatch.setenv("AUTOMONKEY_KEYS", "scancode")
    desk.fg = OTHER
    kf.press("left")
    assert desk.sent == [(VK_LEFT, 0x4B, EXT), (VK_LEFT, 0x4B, EXT | KEYUP),
                         (0, 0x4B, SCANCODE | EXT), (0, 0x4B, SCANCODE | EXT | KEYUP)]


def test_key_down_and_up(desk):
    kf.key_down("shift")
    desk.fg = OTHER  # released even though another program is in front now
    kf.key_up("shift")
    assert desk.sent == [(0, 0x2A, SCANCODE), (0x10, 0x2A, KEYUP)]


# --- focus guard ----------------------------------------------------------------

def test_typing_stops_when_another_program_takes_the_focus(desk):
    def click_elsewhere():
        desk.fg = OTHER

    desk.after_send = click_elsewhere
    with pytest.raises(kf.FocusChanged, match="'Claude Workbench'"):
        kf.write("abc", interval=0)
    assert desk.sent == [(0, ord("a"), UNICODE), (0, ord("a"), UNICODE | KEYUP)]  # 'b' and 'c' not sent


def test_typing_goes_on_in_a_window_of_the_same_program(desk):
    def bar():
        desk.fg = MSTSC + 1  # the connection bar: same process

    desk.after_send = bar
    kf.write("ab", interval=0)
    assert len(desk.sent) == 4


def test_hotkey_checks_the_focus_before_the_chord(desk):
    desk.fg = OTHER
    target = kf._Target()
    desk.fg = MSTSC
    with pytest.raises(kf.FocusChanged):
        target.check()


def test_focus_never_taps_alt_into_a_remote_desktop(monkeypatch):
    from automonkey.ai import windows
    taps = []
    monkeypatch.setattr(windows._u32, "keybd_event", lambda *a: taps.append(a))
    monkeypatch.setattr(kf, "remote_desktop_window", lambda hwnd=None: True)
    windows._alt_tap()
    assert taps == []  # the RDP client would forward it: the remote menu bar would take the next keys
    monkeypatch.setattr(kf, "remote_desktop_window", lambda hwnd=None: False)
    windows._alt_tap()
    assert [a[:2] for a in taps] == [(0x12, 0), (0x12, 0)]


# --- mouse wheel in notches -----------------------------------------------------

def test_scroll_functions_count_wheel_notches(monkeypatch):
    calls = []
    monkeypatch.setattr(ctypes.windll.user32, "mouse_event",
                        lambda flags, dx, dy, data, extra: calls.append((flags, data.value)))
    monkeypatch.setattr(mouse_funcs.pyautogui, "failSafeCheck", lambda: None)
    mouse_funcs.scrollup(3)
    utils.scrolldown(2)
    mouse_funcs.scrollright(1)
    utils.scrollleft(2)
    assert calls == [(0x0800, 360), (0x0800, -240), (0x1000, 120), (0x1000, -240)]


# --- screen grab of one region --------------------------------------------------

def test_gdi_grab_matches_pillow():
    from PIL import ImageChops, ImageGrab

    from automonkey.ai import screen
    x, y, w, h = screen.monitor_rect()
    box = (x + w // 4, y + h // 4, 200, 120)
    ours = screen.gdi_grab(*box)
    theirs = ImageGrab.grab(bbox=(box[0], box[1], box[0] + box[2], box[1] + box[3]), all_screens=True).convert("RGB")
    assert ours.mode == "RGB" and ours.size == (200, 120)
    diff = np.asarray(ImageChops.difference(ours, theirs).convert("L"))
    assert (diff > 8).mean() < 0.05  # same pixels, apart from what changed between the two grabs


def test_gdi_grab_rejects_an_empty_rectangle():
    from automonkey.ai import screen
    with pytest.raises(ValueError):
        screen.gdi_grab(0, 0, 0, 10)
