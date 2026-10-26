"""Linux side of controls.py: the accessibility tree through AT-SPI (gi.repository.Atspi).

Gives controls.py the same three things UI Automation gives it on Windows: the root
element of a window, a cheap snapshot (type, name, id, enabled, box in screenshot pixels)
of each element, and the element with the keyboard focus. Control types are mapped to the
UI Automation names (Button, MenuItem, Edit, ...) so scripts and INTERACTIVE/TEXTUAL work
unchanged on both systems.

Elements that are not SHOWING (closed menus, the hidden list of a combo box, other tab
pages) are skipped with everything under them, like UI Automation does for Qt and GTK:
an open menu is listed while it is open. Qt apps need QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
(`launch` sets it), GTK apps toolkit-accessibility on; see docs/linux_atspi.md.
"""
from __future__ import annotations

import subprocess

from . import screen, windows

# AT-SPI role nicks -> UI Automation control types.
ROLE_TYPES = {
    "push-button": "Button", "toggle-button": "Button", "button": "Button",
    "menu-item": "MenuItem", "check-menu-item": "MenuItem", "radio-menu-item": "MenuItem",
    "tearoff-menu-item": "MenuItem", "popup-menu": "Menu", "menu-bar": "MenuBar",
    "check-box": "CheckBox", "radio-button": "RadioButton", "combo-box": "ComboBox",
    "entry": "Edit", "password-text": "Edit", "spin-button": "Spinner",
    "label": "Text", "static": "Text", "heading": "Text", "paragraph": "Text", "caption": "Text",
    "list": "List", "list-box": "List", "list-item": "ListItem",
    "page-tab": "TabItem", "page-tab-list": "Tab",
    "tree": "Tree", "tree-table": "Tree", "tree-item": "TreeItem",
    "table": "Table", "table-cell": "DataItem", "table-row": "DataItem",
    "table-column-header": "HeaderItem", "column-header": "HeaderItem",
    "table-row-header": "HeaderItem", "row-header": "HeaderItem",
    "link": "Hyperlink", "slider": "Slider", "scroll-bar": "ScrollBar", "progress-bar": "ProgressBar",
    "tool-bar": "ToolBar", "status-bar": "StatusBar", "tool-tip": "ToolTip",
    "frame": "Window", "window": "Window", "dialog": "Window", "alert": "Window", "file-chooser": "Window",
    "image": "Image", "icon": "Image", "separator": "Separator",
    "panel": "Pane", "filler": "Pane", "split-pane": "Pane", "scroll-pane": "Pane", "viewport": "Pane",
    "layered-pane": "Pane", "root-pane": "Pane", "internal-frame": "Pane", "option-pane": "Pane",
    "grouping": "Group", "section": "Group", "form": "Group", "unknown": "Custom",
}
_MENU_ROLES = {"menu", "menu-item", "check-menu-item", "radio-menu-item", "tearoff-menu-item", "popup-menu"}
# Top-level windows of the app that belong to the window being looked at: GTK menus,
# combo popups and tooltips are separate top-levels; dialogs as on Windows (owned windows).
_POPUP_ROLES = {"window", "popup-menu", "menu", "tool-tip", "dialog", "alert", "file-chooser", "list"}

_VIEW_ROLES = {"list", "list-box", "tree", "tree-table", "table"}
_ITEM_ROLES = {"list-item", "tree-item", "table-cell", "table-row", "table-row-header", "row-header"}

MAX_NODES = 6000


def _atspi():
    from ..atspi_funcs import _atspi as load
    return load()


def _states(acc):
    try:
        return acc.get_state_set()
    except Exception:
        return None


def _has(states, Atspi, name: str) -> bool:
    return states is not None and states.contains(getattr(Atspi.StateType, name))


def _role(acc) -> str:
    try:
        return acc.get_role().value_nick
    except Exception:
        return ""


def _name(acc) -> str:
    try:
        return (acc.get_name() or "").strip()
    except Exception:
        return ""


def _children(acc) -> list:
    try:
        n = acc.get_child_count()
    except Exception:
        return []
    kids = []
    for i in range(n):
        try:
            k = acc.get_child_at_index(i)
        except Exception:
            continue
        if k is not None:
            kids.append(k)
    return kids


def _pid(acc) -> int:
    try:
        return acc.get_process_id()
    except Exception:
        return 0


def _apps() -> list:
    return _children(_atspi().get_desktop(0))


def control_type(acc, role: str | None = None, states=None) -> str:
    role = role if role is not None else _role(acc)
    if role == "menu":  # GTK: a submenu title in a menu bar or menu
        return "MenuItem" if _name(acc) else "Menu"
    if role == "text":  # Qt line edits are "text"; read-only text views too
        Atspi = _atspi()
        return "Edit" if _has(states if states is not None else _states(acc), Atspi, "EDITABLE") else "Text"
    if role.startswith("document"):
        return "Document"
    return ROLE_TYPES.get(role) or "".join(p.capitalize() for p in role.split("-")) or "?"


def props(acc) -> dict:
    """The same snapshot controls._props makes from a UI Automation element."""
    Atspi = _atspi()
    states = _states(acc)
    role = _role(acc)
    rect = None
    if _has(states, Atspi, "SHOWING"):
        try:
            e = acc.get_extents(Atspi.CoordType.SCREEN)
            if e.width > 0 and e.height > 0:
                v = screen.view()
                x0, y0 = v.to_image(e.x, e.y)
                x1, y1 = v.to_image(e.x + e.width, e.y + e.height)
                rect = (x0, y0, x1 - x0, y1 - y0)
        except Exception:
            pass
    try:
        auto_id = acc.get_accessible_id() or ""
    except Exception:
        auto_id = ""
    enabled = states is None or _has(states, Atspi, "ENABLED") or _has(states, Atspi, "SENSITIVE")
    return dict(type=control_type(acc, role, states), name=_name(acc), auto_id=auto_id, enabled=enabled,
                rect=rect)


def toggle(acc) -> str:
    """on / off / mixed for check boxes, radio buttons, toggle buttons and checkable menu items."""
    Atspi = _atspi()
    states = _states(acc)
    role = _role(acc)
    if role not in ("check-box", "radio-button", "toggle-button", "check-menu-item", "radio-menu-item") \
            and not _has(states, Atspi, "CHECKABLE"):
        return ""
    if _has(states, Atspi, "INDETERMINATE"):
        return "mixed"
    return "on" if _has(states, Atspi, "CHECKED") or _has(states, Atspi, "PRESSED") else "off"


def _top_levels(pid: int | None = None) -> list:
    tops = []
    for app in _apps():
        if pid and _pid(app) != pid:
            continue
        tops.extend(_children(app))
    return tops


def _showing(acc) -> bool:
    return _has(_states(acc), _atspi(), "SHOWING")


def root(window: str | int):
    """(window dict, its AT-SPI top-level, other showing top-levels of the same process)."""
    w = windows.find_window(window)
    if not _apps():
        raise LookupError("the AT-SPI desktop lists no applications: its registry daemon is not running. "
                          "Usually the accessibility bus was started for another X display (the login "
                          "screen); restart it with `systemctl --user restart at-spi-dbus-bus.service`, "
                          "then restart the app under test")
    tops = [t for t in _top_levels(w.get("pid")) if _showing(t)]
    if not tops and w.get("pid"):
        tops = [t for t in _top_levels() if _showing(t)]
    title = w["title"].strip()
    best = next((t for t in tops if _name(t) == title), None)
    if best is None:
        best = next((t for t in tops if _name(t) and (_name(t) in title or title in _name(t))), None)
    if best is None:
        Atspi = _atspi()
        cx, cy = w["x"] + w["w"] / 2, w["y"] + w["h"] / 2

        def distance(t):
            try:
                e = t.get_extents(Atspi.CoordType.SCREEN)
                return abs(e.x + e.width / 2 - cx) + abs(e.y + e.height / 2 - cy)
            except Exception:
                return float("inf")
        best = min(tops, key=distance, default=None)
    if best is None:
        raise LookupError(f"window {w['title']!r} has no accessibility tree (AT-SPI). Qt apps need "
                          "QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 before they start (`launch` sets it), GTK apps "
                          "`gsettings set org.gnome.desktop.interface toolkit-accessibility true`, Chromium/"
                          "Electron --force-renderer-accessibility; self-drawn UIs have none: use OCR")
    popups = [t for t in tops if t is not best and _role(t) in _POPUP_ROLES and _key(t) != _key(best)]
    return w, best, popups


def _key(acc):
    return (_pid(acc), getattr(acc, "path", None) or id(acc))


def walk(window: str | int, depth: int | None = None, interactive_only: bool = False,
         interactive: set | None = None):
    """Yield (level, accessible, props) like controls.walk; hidden subtrees are skipped."""
    Atspi = _atspi()
    _w, top, popups = root(window)
    stack = [(0, top)] + [(1, p) for p in reversed(popups)]
    seen, budget = set(), MAX_NODES
    while stack and budget > 0:
        level, acc = stack.pop()
        key = _key(acc)
        if key in seen:
            continue
        seen.add(key)
        budget -= 1
        if level and not _has(_states(acc), Atspi, "SHOWING"):
            continue
        if level:
            p = props(acc)
            if not interactive_only or p["type"] in (interactive or ()):
                yield level, acc, p
        if depth is None or level < depth:
            stack.extend((level + 1, k) for k in reversed(_children(acc)))


def _active_pid() -> int:
    try:
        out = subprocess.run(["xdotool", "getactivewindow", "getwindowpid"], capture_output=True, text=True,
                             timeout=3).stdout.strip()
        return int(out) if out.isdigit() else 0
    except (OSError, subprocess.TimeoutExpired):
        return 0


def focused() -> dict:
    """The element with the keyboard focus: the FOCUSED, SHOWING element of the active
    application (its active window first). Qt keeps FOCUSED on the widget behind an open
    menu, so a focused menu item wins over other focused elements."""
    Atspi = _atspi()
    pid = _active_pid()
    tops = [t for t in _top_levels(pid) if _showing(t)] or [t for t in _top_levels() if _showing(t)]
    tops.sort(key=lambda t: not _has(_states(t), Atspi, "ACTIVE"))
    for top in tops:
        found = []
        # (element, whether the nearest list/tree/table above it has the focus)
        stack, budget = [(top, True)], MAX_NODES
        while stack and budget > 0:
            acc, view_focused = stack.pop()
            budget -= 1
            states = _states(acc)
            if acc is not top and not _has(states, Atspi, "SHOWING"):
                continue
            role = _role(acc)
            is_focused = _has(states, Atspi, "FOCUSED")
            # Qt keeps FOCUSED on a view's current item after the view lost the focus.
            if is_focused and (role not in _ITEM_ROLES or view_focused):
                found.append(acc)
            if role in _VIEW_ROLES:
                view_focused = is_focused
            stack.extend((k, view_focused) for k in reversed(_children(acc)))
        if found:
            menus = [a for a in found if _role(a) in _MENU_ROLES]
            return props((menus or found)[-1])
    if tops:
        return props(tops[0])
    raise LookupError("no focused element found (is an accessible app active? see `controls`)")
