"""Unit tests for automonkey.key_funcs that don't send any input."""
import json
import sys

import pytest

pytest.importorskip("pyautogui")

if sys.platform != "win32":
    pytest.skip("layout handling is Windows-specific", allow_module_level=True)

import ctypes

from automonkey import key_funcs as kf

VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12


@pytest.fixture(scope="module")
def german():
    return ctypes.windll.user32.LoadKeyboardLayoutW("00000407", 0)  # load, don't activate


def test_char_keys_qwertz(german):
    assert kf.char_keys("y", german) == [ord("Y")]
    assert kf.char_keys(";", german) == [VK_SHIFT, 0xBC]  # shift + comma key
    assert kf.char_keys("@", german) == [VK_CONTROL, VK_MENU, ord("Q")]  # AltGr+Q
    assert kf.char_keys("^", german) is None  # dead key: typed as Unicode instead
    assert kf.char_keys("\U0001F600", german) is None


def test_shortcut_letters_are_layout_independent(german):
    assert kf._shortcut_vks(["ctrl", "shift", "z"], german) == [VK_CONTROL, VK_SHIFT, ord("Z")]
    assert kf._shortcut_vks(["ctrl", "?"], german) == [VK_CONTROL, VK_SHIFT, 0xDB]
    with pytest.raises(ValueError):
        kf._shortcut_vks(["ctrl", "nosuchkey"], german)


def test_powertoys_remaps(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps(
        {"properties": {"activeConfiguration": {"value": "default"}}}))
    (tmp_path / "default.json").write_text(json.dumps({"remapKeys": {"inProcess": [
        {"originalKeys": "90", "newRemapKeys": "89"},
        {"originalKeys": "89", "newRemapKeys": "90"},
        {"originalKeys": "20", "newRemapKeys": "17;67"},  # key -> shortcut: ignored
    ]}}))
    remaps = kf.powertoys_remaps(str(tmp_path))
    assert remaps == {90: 89, 89: 90}
    assert kf._source_vk(ord("Z"), remaps) == ord("Y")  # inject Y so the app receives Z
    assert kf._source_vk(ord("A"), remaps) == ord("A")


def test_powertoys_remaps_missing_config(tmp_path):
    assert kf.powertoys_remaps(str(tmp_path)) == {}
