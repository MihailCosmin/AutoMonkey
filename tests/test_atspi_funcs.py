"""Unit tests for automonkey.atspi_funcs that don't touch a real AT-SPI bus.

Uses fake Atspi.Role/StateType namespaces and fake Accessible objects instead of the
real gi.repository.Atspi bindings, so these run anywhere (no python3-gi/at-spi2-core
needed) - see tests/test_atspi_integration.py for tests against a real desktop.
"""
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="atspi_funcs is Linux-only")

import automonkey.atspi_funcs as af  # noqa: E402  (after the skip, and after sys.path setup)


# --- fakes -------------------------------------------------------------------------

class _Sentinel:
    """A unique, hashable stand-in for one Atspi.Role / Atspi.StateType member."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<{self.name}>"


class _EnumNamespace:
    def __init__(self, *names):
        for name in names:
            setattr(self, name, _Sentinel(name))


_ROLE_NAMES = (
    "BUTTON", "PUSH_BUTTON", "TOGGLE_BUTTON", "CHECK_BOX", "RADIO_BUTTON", "COMBO_BOX",
    "TEXT", "ENTRY", "PASSWORD_TEXT", "DOCUMENT_TEXT", "DOCUMENT_FRAME", "DOCUMENT_WEB",
    "DOCUMENT_EMAIL", "DOCUMENT_PRESENTATION", "DOCUMENT_SPREADSHEET", "LABEL",
    "MENU_ITEM", "CHECK_MENU_ITEM", "RADIO_MENU_ITEM", "TEAROFF_MENU_ITEM", "MENU",
    "POPUP_MENU", "MENU_BAR", "LIST", "LIST_BOX", "LIST_ITEM", "PAGE_TAB", "PAGE_TAB_LIST",
    "FRAME", "DIALOG",
)
_STATE_NAMES = ("SHOWING", "VISIBLE", "ENABLED", "SENSITIVE", "ACTIVE", "FOCUSED", "CHECKED")


class FakeAtspi:
    """Stands in for gi.repository.Atspi: just enough of the namespace for the pure
    lookup/translation logic in atspi_funcs.py to run against fake accessibles."""

    Role = _EnumNamespace(*_ROLE_NAMES)
    StateType = _EnumNamespace(*_STATE_NAMES)

    class Action:
        @staticmethod
        def get_action_name(acc, i):
            return acc.actions[i]

        @staticmethod
        def do_action(acc, i):
            acc.do_action(i)

    class Text:
        @staticmethod
        def get_text(acc, start, end):
            return acc.text[start:end]

    class Selection:
        @staticmethod
        def select_child(acc, index):
            acc.selected_index = index
            return True


class FakeAccessible:
    def __init__(self, name="", role=None, children=None, actions=None, states=None,
                 text=None, accessible_id=None, attributes=None, toggle_on_action=False,
                 log=None):
        self.name = name
        self.role = role
        self.children = list(children or [])
        self.actions = list(actions or [])
        self.states = set(states or [])
        self.text = text  # None => not a Text-implementing accessible
        self.accessible_id = accessible_id
        self.attributes = dict(attributes or {})
        self.toggle_on_action = toggle_on_action
        self.log = log  # optional shared list: (name, action) appended by do_action
        self.action_log = []
        self.focused = False

    def get_name(self):
        return self.name

    def get_role(self):
        return self.role

    def get_role_name(self):
        return self.role.name.lower().replace("_", " ") if self.role else ""

    def get_child_count(self):
        return len(self.children)

    def get_child_at_index(self, i):
        return self.children[i]

    def get_state_set(self):
        return FakeStateSet(self.states)

    def get_n_actions(self):
        return len(self.actions)

    def do_action(self, i):
        name = self.actions[i]
        self.action_log.append(name)
        if self.log is not None:
            self.log.append((self.name, name))
        if self.toggle_on_action and name in ("click", "toggle"):
            if FakeAtspi.StateType.CHECKED in self.states:
                self.states.discard(FakeAtspi.StateType.CHECKED)
            else:
                self.states.add(FakeAtspi.StateType.CHECKED)

    def get_character_count(self):
        return len(self.text) if self.text is not None else 0

    def is_text(self):
        return self.text is not None

    def set_text_contents(self, value):
        if self.text is None:
            return False
        self.text = value
        return True

    def get_accessible_id(self):
        return self.accessible_id or ""

    def get_attributes(self):
        return self.attributes

    def grab_focus(self):
        self.focused = True
        return True


class FakeStateSet:
    def __init__(self, states):
        self.states = states

    def contains(self, state):
        return state in self.states


@pytest.fixture
def fake_atspi(monkeypatch):
    """Route _prepare() to the fake Atspi namespace, bypassing the real gi import and
    bus-reachability check entirely."""
    monkeypatch.setattr(af, "_prepare", lambda backend: FakeAtspi)
    return FakeAtspi


# --- criteria mapping ---------------------------------------------------------------

def test_roles_for_control_type_known():
    roles = af._roles_for_control_type(FakeAtspi, "Button")
    assert FakeAtspi.Role.BUTTON in roles
    assert FakeAtspi.Role.PUSH_BUTTON in roles


def test_roles_for_control_type_unknown_raises_value_error():
    with pytest.raises(ValueError, match="Frobnicator"):
        af._roles_for_control_type(FakeAtspi, "Frobnicator")


def test_matches_dict_title_and_title_re():
    node = FakeAccessible(name="Save As...")
    assert af._matches_dict(node, {"title": "Save As..."}) is True
    assert af._matches_dict(node, {"title": "Save"}) is False
    assert af._matches_dict(node, {"title_re": "Save.*"}) is True
    assert af._matches_dict(node, {"title_re": "^Open"}) is False


def test_matches_dict_control_type_roles():
    button = FakeAccessible(name="OK", role=FakeAtspi.Role.BUTTON)
    entry = FakeAccessible(name="", role=FakeAtspi.Role.TEXT)
    roles = af._roles_for_control_type(FakeAtspi, "Button")
    assert af._matches_dict(button, {}, control_type_roles=roles) is True
    assert af._matches_dict(entry, {}, control_type_roles=roles) is False


def test_matches_dict_auto_id_falls_back_to_name():
    with_id = FakeAccessible(name="whatever", accessible_id="save-btn")
    without_id = FakeAccessible(name="SaveButtonName", accessible_id=None)
    assert af._matches_dict(with_id, {"auto_id": "save-btn"}) is True
    assert af._matches_dict(without_id, {"auto_id": "SaveButtonName"}) is True
    assert af._matches_dict(without_id, {"auto_id": "something-else"}) is False


def test_get_control_unknown_control_type_raises_value_error_not_lookup_error(fake_atspi, monkeypatch):
    """Regression test: an unknown control_type must surface as ValueError, not get
    silently swallowed by _find_all's per-node exception guard into a confusing
    LookupError (the bug found and fixed while building this - see pywinauto_for_linux.md
    section 3)."""
    window = FakeAccessible(name="Win", children=[FakeAccessible(name="OK", role=FakeAtspi.Role.BUTTON)])
    monkeypatch.setattr(af, "get_window", lambda *a, **k: window)
    with pytest.raises(ValueError, match="Frobnicator"):
        af.get_control("Win", {"control_type": "Frobnicator"})


# --- best match ----------------------------------------------------------------------

def _window_with(*children):
    return FakeAccessible(name="Win", children=list(children))


def test_best_match_exact_name():
    ok = FakeAccessible(name="OK", role=FakeAtspi.Role.BUTTON)
    cancel = FakeAccessible(name="Cancel", role=FakeAtspi.Role.BUTTON)
    win = _window_with(ok, cancel)
    assert af._best_match(FakeAtspi, win, "OK") is ok


def test_best_match_name_plus_role_suffix():
    save = FakeAccessible(name="Save", role=FakeAtspi.Role.BUTTON)
    save_label = FakeAccessible(name="Save", role=FakeAtspi.Role.LABEL)
    win = _window_with(save_label, save)
    assert af._best_match(FakeAtspi, win, "SaveButton") is save


def test_best_match_case_insensitive_substring():
    entry = FakeAccessible(name="Search results", role=FakeAtspi.Role.LABEL)
    win = _window_with(entry)
    assert af._best_match(FakeAtspi, win, "search") is entry


def test_best_match_no_match_returns_none():
    win = _window_with(FakeAccessible(name="OK", role=FakeAtspi.Role.BUTTON))
    assert af._best_match(FakeAtspi, win, "NoSuchControl") is None


# --- menu walk -------------------------------------------------------------------------

def test_select_menu_expands_intermediate_then_invokes_last(fake_atspi, monkeypatch):
    log = []
    save_as = FakeAccessible(name="Save As...", role=FakeAtspi.Role.MENU_ITEM, actions=["click"], log=log)
    file_menu = FakeAccessible(
        name="&File", role=FakeAtspi.Role.MENU, actions=["expand"], children=[save_as], log=log,
    )
    window = FakeAccessible(name="Win", children=[file_menu])
    monkeypatch.setattr(af, "get_window", lambda *a, **k: window)

    af.select_menu("Win", "File -> Save As...")

    assert log == [("&File", "expand"), ("Save As...", "click")]


def test_select_menu_missing_item_raises_lookup_error(fake_atspi, monkeypatch):
    window = FakeAccessible(name="Win", children=[])
    monkeypatch.setattr(af, "get_window", lambda *a, **k: window)
    with pytest.raises(LookupError, match="File"):
        af.select_menu("Win", "File -> Save As...")


# --- check toggle -----------------------------------------------------------------------

@pytest.mark.parametrize("already_checked, want_checked, expect_action", [
    (False, True, True),
    (True, True, False),
    (True, False, True),
    (False, False, False),
])
def test_check_control_toggles_only_when_needed(fake_atspi, monkeypatch, already_checked, want_checked, expect_action):
    states = {FakeAtspi.StateType.CHECKED} if already_checked else set()
    box = FakeAccessible(name="Enable feature", role=FakeAtspi.Role.CHECK_BOX,
                          actions=["click"], states=states, toggle_on_action=True)
    monkeypatch.setattr(af, "get_control", lambda *a, **k: box)

    af.check_control("Win", "Enable feature", want_checked)

    assert (FakeAtspi.StateType.CHECKED in box.states) == want_checked
    assert (len(box.action_log) == 1) == expect_action


def test_check_control_no_toggle_action_raises_value_error(fake_atspi, monkeypatch):
    box = FakeAccessible(name="Enable feature", role=FakeAtspi.Role.CHECK_BOX, actions=[], states=set())
    monkeypatch.setattr(af, "get_control", lambda *a, **k: box)
    with pytest.raises(ValueError, match="no AT-SPI action"):
        af.check_control("Win", "Enable feature", True)


# --- text fallback -----------------------------------------------------------------------

def test_get_control_text_reads_via_text_interface(fake_atspi, monkeypatch):
    entry = FakeAccessible(name="placeholder", role=FakeAtspi.Role.TEXT, text="hello world")
    monkeypatch.setattr(af, "get_control", lambda *a, **k: entry)
    copied = []
    monkeypatch.setattr(af, "copy", copied.append)

    assert af.get_control_text("Win", "Entry") == "hello world"
    assert copied == ["hello world"]


def test_get_control_text_empty_text_field_returns_empty_not_name(fake_atspi, monkeypatch):
    """A legitimately empty text field must return "", not fall back to the
    accessible's name - is_text() is the right check, not character_count() > 0."""
    entry = FakeAccessible(name="placeholder-ish name", role=FakeAtspi.Role.TEXT, text="")
    monkeypatch.setattr(af, "get_control", lambda *a, **k: entry)
    monkeypatch.setattr(af, "copy", lambda *_: None)

    assert af.get_control_text("Win", "Entry") == ""


def test_get_control_text_falls_back_to_name_for_non_text_accessible(fake_atspi, monkeypatch):
    label = FakeAccessible(name="idle", role=FakeAtspi.Role.LABEL, text=None)
    monkeypatch.setattr(af, "get_control", lambda *a, **k: label)
    monkeypatch.setattr(af, "copy", lambda *_: None)

    assert af.get_control_text("Win", "Label") == "idle"


def test_set_control_text_uses_editable_text_when_available(fake_atspi, monkeypatch):
    entry = FakeAccessible(name="", role=FakeAtspi.Role.TEXT, text="old")
    monkeypatch.setattr(af, "get_control", lambda *a, **k: entry)
    calls = []
    monkeypatch.setattr(af, "keys2", lambda *a, **k: calls.append(("keys2", a)))
    monkeypatch.setattr(af, "write", lambda *a, **k: calls.append(("write", a)))

    af.set_control_text("Win", "Entry", text="new")

    assert entry.text == "new"
    assert calls == []  # no select-all+type fallback needed


def test_set_control_text_falls_back_to_select_all_and_type(fake_atspi, monkeypatch):
    non_editable = FakeAccessible(name="", role=FakeAtspi.Role.TEXT, text=None)  # set_text_contents -> False
    monkeypatch.setattr(af, "get_control", lambda *a, **k: non_editable)
    calls = []
    monkeypatch.setattr(af, "keys2", lambda *a, **k: calls.append(("keys2", a)))
    monkeypatch.setattr(af, "write", lambda *a, **k: calls.append(("write", a)))

    af.set_control_text("Win", "Entry", text="typed in")

    assert non_editable.focused is True
    assert calls == [("keys2", ("ctrl", "a")), ("write", ("typed in",))]


# --- key syntax translation --------------------------------------------------------------

@pytest.fixture
def key_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(af, "write", lambda text, **k: calls.append(("write", text)))
    monkeypatch.setattr(af, "press", lambda key: calls.append(("press", key)))
    monkeypatch.setattr(af, "keys2", lambda *keys, **k: calls.append(("keys2", keys)))
    return calls


@pytest.mark.parametrize("text, expected", [
    ("{ENTER}", [("press", "enter")]),
    ("^a", [("keys2", ("ctrl", "a"))]),
    ("%f", [("keys2", ("alt", "f"))]),
    ("+x", [("keys2", ("shift", "x"))]),
    ("~", [("press", "enter")]),
    ("hello", [("write", "hello")]),
    ("^(ab)", [("keys2", ("ctrl", "a")), ("keys2", ("ctrl", "b"))]),
    ("^+s", [("keys2", ("ctrl", "shift", "s"))]),
])
def test_send_key_syntax_translates_pywinauto_syntax(key_calls, text, expected):
    af._send_key_syntax(text, pause=0.0)
    assert key_calls == expected


def test_send_key_syntax_mixed_literal_and_special(key_calls):
    af._send_key_syntax("hi{TAB}there", pause=0.0)
    assert key_calls == [("write", "hi"), ("press", "tab"), ("write", "there")]
