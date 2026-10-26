"""Unit tests for the Linux (AT-SPI) side of the AI layer's accessibility helpers
(automonkey/ai/atspi_tree.py), against fake AT-SPI objects: no desktop needed."""
import itertools
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("pyautogui")

from automonkey.ai import atspi_tree, controls, screen, script, windows

_paths = itertools.count()


class _States:
    def __init__(self, names):
        self.names = set(names)

    def contains(self, state):
        return state in self.names


class _StateType:
    def __getattr__(self, name):
        return name.lower()


FakeAtspi = SimpleNamespace(StateType=_StateType(), CoordType=SimpleNamespace(SCREEN=0))


class Node:
    def __init__(self, role, name="", states=("showing", "enabled"), ext=(0, 0, 10, 10), kids=(), pid=1,
                 aid=""):
        self.role, self.name, self.states, self.ext = role, name, set(states), ext
        self.kids, self.pid, self.aid = list(kids), pid, aid
        self.path = f"/org/a11y/atspi/accessible/{next(_paths)}"

    def get_role(self):
        return SimpleNamespace(value_nick=self.role)

    def get_name(self):
        return self.name

    def get_state_set(self):
        return _States(self.states)

    def get_extents(self, _coord):
        x, y, w, h = self.ext
        return SimpleNamespace(x=x, y=y, width=w, height=h)

    def get_child_count(self):
        return len(self.kids)

    def get_child_at_index(self, i):
        return self.kids[i]

    def get_process_id(self):
        return self.pid

    def get_accessible_id(self):
        return self.aid


@pytest.fixture
def desktop(monkeypatch):
    """Installs a fake desktop; returns a function that sets its applications."""
    apps = []
    FakeAtspi.get_desktop = lambda _n: Node("desktop-frame", kids=apps)
    monkeypatch.setattr(atspi_tree, "_atspi", lambda: FakeAtspi)
    monkeypatch.setattr(screen, "_view", screen.View((1000, 800), max_side=500, origin=(0, 0),
                                                     input_size=(1000, 800)))
    monkeypatch.setattr(atspi_tree, "_active_pid", lambda: 1)

    def set_apps(*new, window=None):
        apps[:] = new
        monkeypatch.setattr(windows, "find_window", lambda _q: window or dict(
            id=1, title="Main", wm_class="app", pid=1, x=0, y=0, w=1000, h=800, active=True))
    return set_apps


def test_control_type_maps_roles_to_ui_automation_names(desktop):
    desktop()
    assert atspi_tree.control_type(Node("push-button")) == "Button"
    assert atspi_tree.control_type(Node("check-menu-item")) == "MenuItem"
    assert atspi_tree.control_type(Node("menu", "File")) == "MenuItem"
    assert atspi_tree.control_type(Node("menu")) == "Menu"
    assert atspi_tree.control_type(Node("text", states=("showing", "editable"))) == "Edit"
    assert atspi_tree.control_type(Node("text")) == "Text"
    assert atspi_tree.control_type(Node("label")) == "Text"
    assert atspi_tree.control_type(Node("document-web")) == "Document"
    assert atspi_tree.control_type(Node("color-chooser")) == "ColorChooser"


def test_props_box_in_screenshot_pixels(desktop):
    desktop()
    p = atspi_tree.props(Node("push-button", " OK ", ext=(100, 200, 80, 40), aid="dlg.ok"))
    assert p == dict(type="Button", name="OK", auto_id="dlg.ok", enabled=True, rect=(50, 100, 40, 20))
    hidden = atspi_tree.props(Node("push-button", "OK", states=("enabled",)))
    assert hidden["rect"] is None
    assert atspi_tree.props(Node("push-button", "OK", states=("showing",)))["enabled"] is False


def test_toggle_states(desktop):
    desktop()
    assert atspi_tree.toggle(Node("check-box", states=("showing", "checked"))) == "on"
    assert atspi_tree.toggle(Node("check-box")) == "off"
    assert atspi_tree.toggle(Node("check-box", states=("indeterminate",))) == "mixed"
    assert atspi_tree.toggle(Node("push-button")) == ""
    assert atspi_tree.toggle(Node("push-button", states=("checkable", "pressed"))) == "on"


def test_walk_skips_hidden_subtrees_and_lists_open_menus(desktop):
    closed = Node("popup-menu", states=("enabled",), kids=[Node("menu-item", "New")])
    file_menu = Node("menu-item", "File", kids=[closed])
    edit_items = Node("popup-menu", kids=[Node("menu-item", "Copy")])
    edit_menu = Node("menu-item", "Edit", kids=[edit_items])
    frame = Node("frame", "Main", kids=[Node("menu-bar", kids=[file_menu, edit_menu]), Node("label", "Ready")])
    desktop(Node("application", "app", kids=[frame]))
    names = [p["name"] for _l, _a, p in atspi_tree.walk("Main")]
    assert names == ["", "File", "Edit", "", "Copy", "Ready"]
    levels = [lvl for lvl, _a, _p in atspi_tree.walk("Main")]
    assert levels == [1, 2, 2, 3, 4, 1]


def test_walk_adds_popup_windows_of_the_same_process_only(desktop):
    frame = Node("frame", "Main", kids=[Node("push-button", "OK")])
    gtk_menu = Node("window", kids=[Node("menu", kids=[Node("menu-item", "Paste")])])
    other = Node("window", pid=2, kids=[Node("menu-item", "Foreign")])
    desktop(Node("application", "app", kids=[frame, gtk_menu]), Node("application", "other", pid=2, kids=[other]))
    names = [p["name"] for _l, _a, p in atspi_tree.walk("Main")]
    assert "Paste" in names and "OK" in names and "Foreign" not in names


def test_root_matches_the_title_then_the_geometry(desktop):
    a = Node("frame", "Other", ext=(0, 0, 100, 100))
    b = Node("frame", "Report.xml - Editor", ext=(500, 400, 300, 200))
    desktop(Node("application", "app", kids=[a, b]), window=dict(
        id=1, title="Report.xml - Editor", wm_class="x", pid=1, x=500, y=400, w=300, h=200, active=True))
    assert atspi_tree.root("Report")[1] is b
    desktop(Node("application", "app", kids=[a, Node("frame", "", ext=(500, 400, 300, 200))]), window=dict(
        id=1, title="Untitled", wm_class="x", pid=1, x=490, y=380, w=320, h=230, active=True))
    assert atspi_tree.root("Untitled")[1].ext == (500, 400, 300, 200)


def test_root_without_tree_explains_how_to_enable_it(desktop):
    desktop(Node("application", "app", kids=[]))
    with pytest.raises(LookupError, match="QT_LINUX_ACCESSIBILITY_ALWAYS_ON"):
        atspi_tree.root("Main")


def test_focused_ignores_items_of_a_view_without_focus(desktop):
    # Qt keeps FOCUSED on a list's current item after Tab moved the focus elsewhere.
    lst = Node("list", kids=[Node("list-item", "Alpha", states=("showing", "focused"))])
    check = Node("check-box", "Enabled", states=("showing", "focused"))
    desktop(Node("application", "app", kids=[Node("frame", "Main", states=("showing", "active"),
                                                   kids=[check, lst])]))
    assert atspi_tree.focused()["name"] == "Enabled"
    lst.states.add("focused")
    check.states.discard("focused")
    assert atspi_tree.focused()["name"] == "Alpha"


def test_focused_prefers_an_open_menu_and_skips_hidden_elements(desktop):
    hidden = Node("list", states=("enabled",), kids=[Node("list-item", "Red", states=("showing", "focused"))])
    edit = Node("text", "name", states=("showing", "focused", "editable"))
    menu = Node("menu-item", "File", states=("showing", "focused"))
    desktop(Node("application", "app", kids=[Node("frame", "Main", kids=[Node("menu-bar", kids=[menu]),
                                                                         edit, hidden])]))
    assert atspi_tree.focused()["name"] == "File"
    menu.states.discard("focused")
    assert atspi_tree.focused()["name"] == "name"


@pytest.mark.skipif(sys.platform == "win32", reason="controls uses UI Automation on Windows")
def test_controls_find_and_tree_use_atspi_on_linux(desktop):
    frame = Node("frame", "Main", kids=[Node("text", "", states=("showing", "editable"),
                                             aid="QApplication.Main.splitter.nameEdit"),
                                        Node("check-box", "Enabled", states=("showing", "checked"))])
    desktop(Node("application", "app", kids=[frame]))
    assert controls.find("Main", "nameEdit")["type"] == "Edit"
    assert "CheckBox 'Enabled'" in controls.tree("Main") and "toggle=on" in controls.tree("Main")


def test_expect_focus_matches_the_last_part_of_a_qt_id(monkeypatch):
    monkeypatch.setattr(controls, "focused", lambda: dict(type="Edit", name="", enabled=True, rect=None,
                                                          auto_id="QApplication.Main.splitter.nameEdit"))
    monkeypatch.setattr(script, "EXPECT_TIMEOUT", 0)
    assert script.run_step("expect_focus nameEdit").startswith("focus on")
    with pytest.raises(script.StepError):
        script.run_step("expect_focus Edit")


def test_windows_venv_commands_run_on_linux():
    p = windows._posix_command
    assert p(r".venv\Scripts\pythonw.exe tests\apps\qt_target.py") == ".venv/bin/python tests/apps/qt_target.py"
    assert p(r"venv\Scripts\python -m pkg") == "venv/bin/python -m pkg"
    assert p(r"xterm -e echo a\ b") == r"xterm -e echo a\ b"
    assert p(".venv/bin/python x.py") == ".venv/bin/python x.py"


def test_root_with_an_empty_desktop_names_the_registry_fix(desktop):
    desktop()
    with pytest.raises(LookupError, match="at-spi-dbus-bus"):
        atspi_tree.root("Main")
