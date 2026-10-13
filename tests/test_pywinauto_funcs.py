"""Unit tests for automonkey.pywinauto_funcs that don't touch real windows."""
import sys

import pytest

pytest.importorskip("pyautogui")

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="pywinauto_funcs is Windows-only")

import automonkey.automonkey as am
from automonkey import pywinauto_funcs as pf


class FakeSpec:
    def __init__(self):
        self.criteria = None

    def child_window(self, **criteria):
        self.criteria = criteria
        return self


class FakeToggle:
    def __init__(self, state):
        self.state = state

    def get_toggle_state(self):
        return self.state

    def toggle(self):
        self.state = 1 - self.state


class FakeMenuItem:
    def __init__(self, name, log):
        self.name, self.log = name, log

    def window_text(self):
        return self.name

    def expand(self):
        self.log.append(("expand", self.name))

    def invoke(self):
        self.log.append(("invoke", self.name))


class FakeMenuWindow:
    def __init__(self, names, log):
        self.items = [FakeMenuItem(_, log) for _ in names]

    def descendants(self, control_type):
        assert control_type == "MenuItem"
        return self.items


def test_escape_keys_types_special_characters_literally():
    assert pf._escape_keys("a+b^(c){d}%~ x") == "a{+}b{^}{(}c{)}{{}d{}}{%}{~} x"


def test_control_spec():
    win = FakeSpec()
    assert pf._control_spec(win, None) is win and win.criteria is None
    pf._control_spec(win, "SaveButton")
    assert win.criteria == {"best_match": "SaveButton"}
    pf._control_spec(win, {"title": "Save", "control_type": "Button"})
    assert win.criteria == {"title": "Save", "control_type": "Button"}


@pytest.mark.parametrize("state, checked, expected", [(0, True, 1), (1, True, 1), (1, False, 0), (0, False, 0)])
def test_check_control_uia_toggle(monkeypatch, state, checked, expected):
    box = FakeToggle(state)
    monkeypatch.setattr(pf, "get_control", lambda *args: box)
    pf.check_control("Window", "Box", checked)
    assert box.state == expected


def test_get_control_text_falls_back_to_texts(monkeypatch):
    class Label:
        def texts(self):
            return ["", "line 1", "line 2"]

    copied = []
    monkeypatch.setattr(pf, "get_control", lambda *args: Label())
    monkeypatch.setattr(pf, "copy", copied.append)
    assert pf.get_control_text("Window", "Label") == "line 1\nline 2"
    assert copied == ["line 1\nline 2"]


def test_walk_menu_expands_then_invokes():
    log = []
    win = FakeMenuWindow(["&File", "Edit", "Select all"], log)
    pf._walk_menu(win, "edit -> Select All", timeout=0)
    assert log == [("expand", "Edit"), ("invoke", "Select all")]


def test_chain_control_actions(monkeypatch):
    calls = []
    monkeypatch.setattr(am, "click_control", lambda *a, **k: calls.append(("click_control", a, k)))
    monkeypatch.setattr(am, "list_controls", lambda *a, **k: calls.append(("list_controls", a, k)))
    am.chain(
        dict(click_control=("Notepad", "File")),
        dict(click_control=dict(window="Notepad", control={"title": "OK"}, invoke=True)),
        dict(list_controls="Notepad"),
    )
    assert calls == [
        ("click_control", ("Notepad", "File"), {}),
        ("click_control", (), {"window": "Notepad", "control": {"title": "OK"}, "invoke": True}),
        ("list_controls", ("Notepad",), {}),
    ]


def test_missing_pywinauto_message(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_pywinauto(name, *args, **kwargs):
        if name == "pywinauto":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pywinauto)
    with pytest.raises(ImportError, match="pip install pywinauto"):
        pf.get_window("Notepad")
