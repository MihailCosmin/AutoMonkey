"""Control-level Linux automation based on AT-SPI (gi.repository.Atspi).

Mirrors the public functions and signatures of pywinauto_funcs.py so a `chain` script
using the control actions (click_control, type_in_control, ...) runs on both Windows
and Linux unchanged. See DONE.md for the implementation notes and the
known limits (Qt/Chrome/Electron accessibility flags, Wayland mouse-click fallback, ...).

Every function takes:
    window: title of the top-level window (regex, matched anywhere in the title,
        like focus/close/minimize) or an Atspi.Accessible already resolved by get_window.
    control: what to act on inside the window:
        - None: the window itself
        - str: "best match" name (see get_control, section 3)
        - dict: search criteria, e.g. {"title": "Save", "control_type": "Button"}
    backend: "atspi" (default and only backend on Linux).
    timeout: seconds to wait for the window/control to appear.

Use list_controls(window) to see the names of the controls in a window.
AT-SPI needs distro packages, not pip: python3-gi, gir1.2-atspi-2.0, at-spi2-core
(Debian/Ubuntu/Raspberry Pi OS: `sudo apt-get install python3-gi gir1.2-atspi-2.0 at-spi2-core`),
plus accessibility enabled: `gsettings set org.gnome.desktop.interface toolkit-accessibility true`
(restart apps started before that for it to take effect). Also make sure the app is not
launched with NO_AT_BRIDGE=1 in its environment - that silently disables AT-SPI registration.
"""
import os
import re
import shlex
import subprocess
import sys
import time
import warnings

import pyautogui

from .key_funcs import write
from .key_funcs import press
from .key_funcs import hotkey as keys2
from .utils import copy

_VALID_BACKENDS = ("atspi", None)

# pywinauto control_type -> AT-SPI Role enum member names (not the display strings from
# get_role_name(), which differ by toolkit/version - see DONE.md findings).
# Not exhaustive; extend as new control_type values are needed.
_CONTROL_TYPE_TO_ROLES = {
    "Button": ("BUTTON", "PUSH_BUTTON", "TOGGLE_BUTTON"),
    "CheckBox": ("CHECK_BOX",),
    "RadioButton": ("RADIO_BUTTON",),
    "ComboBox": ("COMBO_BOX",),
    "Edit": ("TEXT", "ENTRY", "PASSWORD_TEXT"),
    "Document": (
        "DOCUMENT_TEXT", "DOCUMENT_FRAME", "DOCUMENT_WEB", "DOCUMENT_EMAIL",
        "DOCUMENT_PRESENTATION", "DOCUMENT_SPREADSHEET",
    ),
    "Static": ("LABEL",),
    "Text": ("LABEL", "TEXT"),
    "MenuItem": ("MENU_ITEM", "CHECK_MENU_ITEM", "RADIO_MENU_ITEM", "TEAROFF_MENU_ITEM"),
    "Menu": ("MENU", "POPUP_MENU"),
    "MenuBar": ("MENU_BAR",),
    "List": ("LIST", "LIST_BOX"),
    "ListItem": ("LIST_ITEM",),
    "Tab": ("PAGE_TAB",),
    "TabControl": ("PAGE_TAB_LIST",),
    "Window": ("FRAME", "DIALOG"),
    "Dialog": ("DIALOG",),
}

# Keep lookups fast on huge trees (e.g. a browser's page content): cap how deep and how
# many nodes a single find walks, per DONE.md section 3.
_MAX_SEARCH_DEPTH = 40
_MAX_SEARCH_NODES = 6000

_CLOSEST_NAMES_LIMIT = 20

_QT_CHROME_ELECTRON_HINT = (
    "If this looks like the whole app, not just one control: some toolkits don't expose "
    "AT-SPI by default. Qt apps need QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 in their environment "
    "before they start; Chrome/Electron apps need the --force-renderer-accessibility flag; "
    "self-drawn/custom-rendered UIs (e.g. some games, canvas-based apps) cannot expose a tree "
    "at all. See DONE.md known limits."
)

# Set once _atspi() has confirmed the bus is reachable and warned (if needed) about
# toolkit-accessibility - so that check only runs once per process, not on every call.
_env_checked = False


def _check_backend(backend: str):
    if backend not in _VALID_BACKENDS:
        raise ValueError(
            f"backend={backend!r} is not valid on Linux. Use backend='atspi' (the default, "
            "can also be omitted) here; 'uia'/'win32' are pywinauto backends for Windows "
            "(automonkey/pywinauto_funcs.py)."
        )


def _atspi_bus_reachable():
    """Best-effort, SAFE pre-flight check for the AT-SPI D-Bus service (org.a11y.Bus),
    run via a separate dbus-send process rather than libatspi/Atspi itself: when the bus
    is genuinely unreachable, libatspi's C layer prints a fatal "dbind-ERROR" and aborts
    the *entire process* - there is no Python exception to catch, so Atspi.get_desktop()
    (or anything that calls it) must never be the thing that finds this out. Returns
    True/False, or None if the check itself could not run (e.g. no dbus-send installed) -
    that's "inconclusive", not "unreachable", so callers should not hard-fail on None."""
    try:
        result = subprocess.run(
            ["dbus-send", "--session", "--dest=org.a11y.Bus", "--type=method_call",
             "--print-reply", "/org/a11y/bus", "org.a11y.Bus.GetAddress"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.returncode == 0


def _check_accessibility_enabled():
    """Best-effort, warn-only: GNOME's toolkit-accessibility gsetting being off means
    GTK apps won't register on AT-SPI until it's turned on and they're restarted. Not
    every desktop has this schema (this box is labwc/Raspberry Pi Desktop, not GNOME,
    yet the key still applies since GTK itself reads it) - a missing schema is silently
    not a problem, since most AT-SPI apps that matter are GTK and respect this key."""
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "toolkit-accessibility"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if result.returncode == 0 and result.stdout.strip() == "false":
        warnings.warn(
            "org.gnome.desktop.interface toolkit-accessibility is 'false'. GTK apps "
            "already running won't register on AT-SPI until it's enabled AND they're "
            "restarted: gsettings set org.gnome.desktop.interface toolkit-accessibility true",
            stacklevel=3,
        )


def _atspi():
    """Lazily import gi.repository.Atspi, with a clear error if it is missing or if this
    is macOS (not implemented there yet). Also runs the one-time environment checks
    above before returning, so every public function gets a clear, safe error/warning
    up front instead of either a confusing "not found" or - far worse - a process abort
    the first time something actually calls into Atspi against a dead bus."""
    if sys.platform == "darwin":
        raise NotImplementedError(
            "Control actions are not implemented on macOS yet. They are available on "
            "Windows (backend='uia'/'win32', pywinauto_funcs.py) and Linux "
            "(backend='atspi', this module)."
        )
    try:
        import gi  # pylint: disable=import-outside-toplevel
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi  # pylint: disable=import-outside-toplevel
    except (ImportError, ValueError) as err:
        raise ImportError(
            "This function needs the AT-SPI Python bindings (Linux only). Install the "
            "distro packages, e.g. on Debian/Ubuntu/Raspberry Pi OS: "
            "sudo apt-get install python3-gi gir1.2-atspi-2.0 at-spi2-core; then enable "
            "accessibility: gsettings set org.gnome.desktop.interface toolkit-accessibility true"
        ) from err

    global _env_checked  # pylint: disable=global-statement
    if not _env_checked:
        if _atspi_bus_reachable() is False:
            raise ConnectionError(
                "The AT-SPI accessibility bus is not reachable. Make sure at-spi2-core is "
                "installed and the session D-Bus is running: sudo apt-get install "
                "at-spi2-core; then log out and back in (or restart the session) - it is "
                "D-Bus-activated, so installing it is usually enough without a reboot."
            )
        _check_accessibility_enabled()
        _env_checked = True  # only after a successful (or inconclusive) check, so a
        # transient failure (e.g. fixed mid-session) gets re-checked on the next call

    return Atspi


def _prepare(backend: str):
    """Shared validation every public function runs first: checks the backend name,
    then lazily imports Atspi (raising the errors documented in _check_backend/_atspi)."""
    _check_backend(backend)
    return _atspi()


def _safe_name(acc) -> str:
    try:
        return acc.get_name() or ""
    except Exception:  # pylint: disable=broad-except
        return ""


def _safe_role_name(acc) -> str:
    try:
        return acc.get_role_name() or ""
    except Exception:  # pylint: disable=broad-except
        return "?"


def _has_no_children(acc) -> bool:
    try:
        return acc.get_child_count() == 0
    except Exception:  # pylint: disable=broad-except
        return False


def _is_showing(Atspi, acc) -> bool:
    try:
        states = acc.get_state_set()
        return states.contains(Atspi.StateType.SHOWING) or states.contains(Atspi.StateType.VISIBLE)
    except Exception:  # pylint: disable=broad-except
        return False


def _iter_top_level_windows():
    """Yield every top-level window (direct child of every application) across the
    whole AT-SPI desktop - get_window searches "across all applications"."""
    Atspi = _atspi()
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        try:
            app = desktop.get_child_at_index(i)
        except Exception:  # pylint: disable=broad-except
            continue
        if app is None:
            continue
        try:
            n = app.get_child_count()
        except Exception:  # pylint: disable=broad-except
            continue
        for j in range(n):
            try:
                win = app.get_child_at_index(j)
            except Exception:  # pylint: disable=broad-except
                continue
            if win is not None:
                yield win


def _walk(root, visit, max_depth: int = _MAX_SEARCH_DEPTH, max_nodes: int = _MAX_SEARCH_NODES):
    """Depth-first walk from root calling visit(node) on each node, including root.
    Stops past max_depth or once max_nodes nodes have been visited, so a huge subtree
    (e.g. a browser's page content) cannot make a single lookup slow."""
    budget = [max_nodes]

    def _rec(node, depth):
        if node is None or budget[0] <= 0:
            return
        budget[0] -= 1
        visit(node)
        if depth >= max_depth or budget[0] <= 0:
            return
        try:
            n = node.get_child_count()
        except Exception:  # pylint: disable=broad-except
            return
        for i in range(n):
            if budget[0] <= 0:
                return
            try:
                child = node.get_child_at_index(i)
            except Exception:  # pylint: disable=broad-except
                continue
            _rec(child, depth + 1)

    _rec(root, 0)


def _find_all(root, predicate, max_depth: int = _MAX_SEARCH_DEPTH, max_nodes: int = _MAX_SEARCH_NODES):
    found = []

    def visit(node):
        try:
            if predicate(node):
                found.append(node)
        except Exception:  # pylint: disable=broad-except
            pass

    _walk(root, visit, max_depth, max_nodes)
    return found


def _collect_names(root, limit: int = _CLOSEST_NAMES_LIMIT):
    """For error messages: the names actually present under root, for "closest match" hints."""
    names = []

    def visit(node):
        name = _safe_name(node)
        if name:
            names.append(f"{name!r} ({_safe_role_name(node)})")

    _walk(root, visit)
    # de-duplicate while keeping order
    seen = set()
    unique = []
    for entry in names:
        if entry not in seen:
            seen.add(entry)
            unique.append(entry)
    return unique[:limit]


def _roles_for_control_type(Atspi, control_type: str):
    try:
        role_names = _CONTROL_TYPE_TO_ROLES[control_type]
    except KeyError as err:
        raise ValueError(
            f"control_type={control_type!r} is not mapped to an AT-SPI role. Known: "
            f"{sorted(_CONTROL_TYPE_TO_ROLES)}. Extend _CONTROL_TYPE_TO_ROLES in "
            "atspi_funcs.py, or match on a role name directly."
        ) from err
    roles = tuple(getattr(Atspi.Role, name) for name in role_names if hasattr(Atspi.Role, name))
    if not roles:
        raise ValueError(
            f"None of the AT-SPI roles for control_type={control_type!r} ({role_names}) "
            "exist in this Atspi binding version."
        )
    return roles


def _accessible_id(acc):
    """AT-SPI accessible-id (2.34+), else an "id" attribute, else None (caller falls
    back to matching on the accessible name - see DONE.md section 3)."""
    try:
        acc_id = acc.get_accessible_id()
        if acc_id:
            return acc_id
    except Exception:  # pylint: disable=broad-except
        pass
    try:
        attrs = acc.get_attributes()
        if attrs and attrs.get("id"):
            return attrs["id"]
    except Exception:  # pylint: disable=broad-except
        pass
    return None


def _matches_dict(node, criteria: dict, control_type_roles=None) -> bool:
    """criteria is matched as-is except "control_type", which the caller must resolve to
    a roles tuple up front (via _roles_for_control_type) and pass as control_type_roles -
    resolving it here, inside the per-node predicate, would let an unknown control_type's
    ValueError get silently swallowed by _find_all's per-node exception guard instead of
    surfacing as the clear error it should be."""
    if "title" in criteria and _safe_name(node) != criteria["title"]:
        return False
    if "title_re" in criteria and not re.match(criteria["title_re"], _safe_name(node)):
        return False
    if control_type_roles is not None:
        try:
            if node.get_role() not in control_type_roles:
                return False
        except Exception:  # pylint: disable=broad-except
            return False
    for key in ("auto_id", "id"):
        if key in criteria:
            wanted = criteria[key]
            acc_id = _accessible_id(node)
            actual = acc_id if acc_id is not None else _safe_name(node)
            if actual != wanted:
                return False
    return True


def _best_match(Atspi, win, control: str):
    """pywinauto-style "best match": exact name, then name + known control-type suffix
    (e.g. "SaveButton" -> name "Save" with a Button role), then case-insensitive substring."""
    exact = _find_all(win, lambda n: _safe_name(n) == control)
    if exact:
        return exact[0]

    for suffix in sorted(_CONTROL_TYPE_TO_ROLES, key=len, reverse=True):
        if control.endswith(suffix) and len(control) > len(suffix):
            name_part = control[: -len(suffix)]
            roles = _roles_for_control_type(Atspi, suffix)
            matches = _find_all(
                win,
                lambda n, name_part=name_part, roles=roles: (
                    _safe_name(n) == name_part and n.get_role() in roles
                ),
            )
            if matches:
                return matches[0]

    lowered = control.lower()
    substr = _find_all(win, lambda n: lowered in _safe_name(n).lower())
    if substr:
        return substr[0]

    return None


_INVOKE_ACTION_NAMES = ("click", "press", "activate", "jump")
_EXPAND_ACTION_NAMES = ("expand", "open", "click", "activate")
_TOGGLE_ACTION_NAMES = ("click", "toggle")

# pywinauto's special-key names ({ENTER}, {TAB}, ...) -> the names press()/key_funcs expects.
_SPECIAL_KEY_MAP = {
    "ENTER": "enter", "TAB": "tab", "ESC": "esc", "ESCAPE": "esc",
    "BACKSPACE": "backspace", "BKSP": "backspace", "DELETE": "delete", "DEL": "delete",
    "HOME": "home", "END": "end", "INSERT": "insert", "INS": "insert",
    "UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
    "PGUP": "pageup", "PGDN": "pagedown", "SPACE": "space",
    **{f"F{i}": f"f{i}" for i in range(1, 13)},
}
_MOD_CHARS = {"^": "ctrl", "%": "alt", "+": "shift"}

_ROLE_TO_CONTROL_TYPE_CACHE = {}

_STATE_WORD_TO_ATSPI = {
    "visible": ("SHOWING",),
    "enabled": ("ENABLED", "SENSITIVE"),
    "active": ("ACTIVE", "FOCUSED"),
}


def _action_names(Atspi, acc) -> list:
    try:
        n = acc.get_n_actions()
    except Exception:  # pylint: disable=broad-except
        return []
    names = []
    for i in range(n):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                names.append(Atspi.Action.get_action_name(acc, i) or "")
        except Exception:  # pylint: disable=broad-except
            names.append("")
    return names


def _do_action_named(Atspi, acc, preferred_names, default_index=0) -> bool:
    """Run the first action matching one of preferred_names (case-insensitive), else
    default_index if it exists at all. Returns whether an action actually ran."""
    names = _action_names(Atspi, acc)
    if not names:
        return False
    lowered = [n.lower() for n in names]
    for wanted in preferred_names:
        if wanted in lowered:
            Atspi.Action.do_action(acc, lowered.index(wanted))
            return True
    if 0 <= default_index < len(names):
        Atspi.Action.do_action(acc, default_index)
        return True
    return False


def _invoke(Atspi, ctrl):
    if not _do_action_named(Atspi, ctrl, _INVOKE_ACTION_NAMES):
        raise ValueError(
            f"{_safe_name(ctrl)!r} ({_safe_role_name(ctrl)}) has no AT-SPI action to invoke."
        )


def _grab_focus(Atspi, ctrl):
    """Component.grab_focus() first; if it fails, fall back to a real mouse click on the
    control's extents (works on X11/Xwayland; same Wayland caveat as click_control).

    Needed in practice, not just in theory: confirmed `grab_focus()` fails app-wide on
    gnome-text-editor (GTK4) - even on a plain button, not just the text widget - with a
    bare `atspi_error` and no further detail. Rather than treat that as fatal, fall back
    to establishing focus the same way a real user would: by clicking it."""
    try:
        if ctrl.grab_focus():
            return
    except Exception:  # pylint: disable=broad-except
        pass
    try:
        _click_at_extents(Atspi, ctrl, "left", False)
    except Exception as err:  # pylint: disable=broad-except
        raise ValueError(
            f"Could not focus {_safe_name(ctrl)!r} ({_safe_role_name(ctrl)}): "
            f"grab_focus() failed and the click-to-focus fallback also failed ({err})."
        ) from err


def _build_role_to_control_type(Atspi) -> dict:
    mapping = {}
    for ctype, role_names in _CONTROL_TYPE_TO_ROLES.items():
        for name in role_names:
            role = getattr(Atspi.Role, name, None)
            if role is not None and role not in mapping:
                mapping[role] = ctype
    return mapping


def _role_to_control_type(Atspi, node):
    if not _ROLE_TO_CONTROL_TYPE_CACHE:
        _ROLE_TO_CONTROL_TYPE_CACHE.update(_build_role_to_control_type(Atspi))
    try:
        return _ROLE_TO_CONTROL_TYPE_CACHE.get(node.get_role())
    except Exception:  # pylint: disable=broad-except
        return None


def _send_key_syntax(text: str, pause: float):
    """Translate pywinauto key syntax ({ENTER}, ^a, %f, +x, ~, parens groups) to key
    presses via key_funcs. Not a full pywinauto-grammar implementation (no repeat
    counts like "{TAB 3}", no nested groups) - covers the documented cases."""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _MOD_CHARS:
            mods = []
            while i < n and text[i] in _MOD_CHARS:
                mods.append(_MOD_CHARS[text[i]])
                i += 1
            if i >= n:
                break
            if text[i] == "(":
                j = text.index(")", i)
                group, i = text[i + 1:j], j + 1
                for gch in group:
                    keys2(*mods, gch)
                    if pause:
                        time.sleep(pause)
            elif text[i] == "{":
                j = text.index("}", i)
                name, i = text[i + 1:j], j + 1
                keys2(*mods, _SPECIAL_KEY_MAP.get(name.upper(), name.lower()))
            else:
                keys2(*mods, text[i])
                i += 1
            if pause:
                time.sleep(pause)
        elif ch == "{":
            j = text.index("}", i)
            name, i = text[i + 1:j], j + 1
            press(_SPECIAL_KEY_MAP.get(name.upper(), name.lower()))
            if pause:
                time.sleep(pause)
        elif ch == "~":
            press("enter")
            i += 1
            if pause:
                time.sleep(pause)
        elif ch == "(":
            j = text.index(")", i)
            write(text[i + 1:j], interval=pause or 0.01)
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in _MOD_CHARS and text[j] not in "{}~()":
                j += 1
            write(text[i:j], interval=pause or 0.01)
            i = j


def _is_wayland_session() -> bool:
    """Coarse, session-wide check (not per-window) - good enough for the documented
    "Wayland: screen coordinates / mouse clicks don't work" limitation."""
    return bool(os.environ.get("WAYLAND_DISPLAY")) and os.environ.get("XDG_SESSION_TYPE", "").lower() != "x11"


def _click_at_extents(Atspi, ctrl, button: str, double: bool):
    """Mouse click at the control's screen extents (works on X11/Xwayland). On a Wayland
    session this is unreliable (no arbitrary pointer warping) - callers should check
    _is_wayland_session() first and fall back to _invoke()."""
    try:
        extents = ctrl.get_extents(Atspi.CoordType.SCREEN)
    except Exception as err:  # pylint: disable=broad-except
        raise ValueError(
            f"Could not get screen extents of {_safe_name(ctrl)!r} ({_safe_role_name(ctrl)}): {err}. "
            "Try click_control(invoke=True) instead."
        ) from err
    x, y = extents.x + extents.width // 2, extents.y + extents.height // 2
    clicks = 2 if double else 1
    pyautogui.click(x, y, clicks=clicks, button=button)


_MENU_ROLE_NAMES = ("MENU", "MENU_ITEM", "CHECK_MENU_ITEM", "RADIO_MENU_ITEM", "POPUP_MENU", "TEAROFF_MENU_ITEM")


def _find_menu_item(Atspi, root, name: str):
    target = name.replace("&", "").strip().lower()
    roles = tuple(getattr(Atspi.Role, n) for n in _MENU_ROLE_NAMES if hasattr(Atspi.Role, n))

    def matches(node):
        return node.get_role() in roles and _safe_name(node).replace("&", "").strip().lower() == target

    found = _find_all(root, matches)
    return found[0] if found else None


def _expand_menu(Atspi, item):
    _do_action_named(Atspi, item, _EXPAND_ACTION_NAMES)


def _state_satisfied(Atspi, ctrl, words) -> bool:
    try:
        states = ctrl.get_state_set()
    except Exception:  # pylint: disable=broad-except
        return False
    for word in words:
        wanted = _STATE_WORD_TO_ATSPI.get(word)
        if wanted is None:
            continue  # "exists"/"ready": having ctrl already covers "exists" and
            # "ready" is expanded into "visible enabled" by the caller.
        if not any(states.contains(getattr(Atspi.StateType, w)) for w in wanted if hasattr(Atspi.StateType, w)):
            return False
    return True


def get_window(window, backend: str = "atspi", timeout: float = 10):
    """Find a top-level window and wait until it is visible.

    Args:
        window (str): title of the window, regex matched anywhere in the title.
            An already-resolved Atspi.Accessible is returned as it is.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the window. Defaults to 10.

    Returns:
        Atspi.Accessible: the top-level window (frame/dialog), for anything not
            covered by these functions.

    Raises:
        LookupError: if no matching, visible window is found within timeout.
    """
    Atspi = _prepare(backend)
    if not isinstance(window, str):
        return window

    pattern = f".*?{window}.*?"
    deadline = time.monotonic() + timeout
    seen = []
    while True:
        seen = []
        for win in _iter_top_level_windows():
            name = _safe_name(win)
            seen.append(name)
            if re.match(pattern, name) and _is_showing(Atspi, win):
                return win
        if time.monotonic() >= deadline:
            break
        time.sleep(0.2)

    seen_unique = sorted({name for name in seen if name})
    raise LookupError(
        f"No visible window matching {window!r} found within {timeout}s. "
        f"Windows seen: {seen_unique or '<none>'}"
    )


def get_control(window, control=None, backend: str = "atspi", timeout: float = 10):
    """Find a control inside a window and wait until it exists.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict, optional): best-match name or search criteria.
            None returns the window itself.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait. Defaults to 10.

    Returns:
        Atspi.Accessible: the control.

    Raises:
        LookupError: if no matching control is found within timeout.
    """
    Atspi = _prepare(backend)
    win = get_window(window, backend, timeout)
    if control is None:
        return win

    if isinstance(control, dict):
        criteria = dict(control)
        found_index = criteria.pop("found_index", 0)
        control_type_roles = None
        if "control_type" in criteria:
            control_type_roles = _roles_for_control_type(Atspi, criteria.pop("control_type"))

    deadline = time.monotonic() + timeout
    while True:
        if isinstance(control, dict):
            matches = _find_all(win, lambda n: _matches_dict(n, criteria, control_type_roles))
            if len(matches) > found_index:
                return matches[found_index]
        else:
            match = _best_match(Atspi, win, control)
            if match is not None:
                return match
        if time.monotonic() >= deadline:
            break
        time.sleep(0.2)

    message = (
        f"Control not found in window {_safe_name(win)!r}: {control!r}. "
        f"Closest names seen: {_collect_names(win) or '<none>'}"
    )
    if _has_no_children(win):
        message += " " + _QT_CHROME_ELECTRON_HINT
    raise LookupError(message)


def start_app(command: str, backend: str = "atspi", timeout: float = 10):
    """Start an application and wait until it appears on the AT-SPI bus.

    Args:
        command (str): command line to start the application.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the app to be ready. Defaults to 10.

    Returns:
        Atspi.Accessible: the application.

    Raises:
        LookupError: if the app does not appear on the AT-SPI bus within timeout.
    """
    Atspi = _prepare(backend)
    args = shlex.split(command) if isinstance(command, str) else command
    # Detached: inheriting the caller's stdin/stdout/stderr/session would make the app's
    # own lifetime hold those pipes open - e.g. a caller piping/capturing a script's
    # output would see it hang until the (possibly long-running, GUI) app exits, found
    # while testing this against real gnome-calculator/gnome-text-editor.
    proc = subprocess.Popen(  # pylint: disable=consider-using-with
        args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.monotonic() + timeout
    while True:
        desktop = Atspi.get_desktop(0)
        for i in range(desktop.get_child_count()):
            try:
                app = desktop.get_child_at_index(i)
                if app is not None and app.get_process_id() == proc.pid:
                    return app
            except Exception:  # pylint: disable=broad-except
                continue
        if time.monotonic() >= deadline:
            break
        time.sleep(0.2)

    raise LookupError(
        f"{command!r} (pid {proc.pid}) did not appear on the AT-SPI bus within {timeout}s. "
        "The app may not expose accessibility - see DONE.md known limits."
    )


def click_control(window, control=None, button: str = "left", double: bool = False,
                  invoke: bool = False, backend: str = "atspi", timeout: float = 10):
    """Click a control.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict, optional): the control to click. None clicks the window.
        button (str, optional): "left", "right" or "middle". Defaults to "left".
            Only meaningful when invoke=False (X11; see DONE.md known limits).
        double (bool, optional): double click. Defaults to False.
        invoke (bool, optional): run the control's AT-SPI "click"/"press"/"activate" action
            instead of a mouse click. Works on Wayland too. Defaults to False.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    Atspi = _prepare(backend)
    ctrl = get_control(window, control, backend, timeout)
    if invoke:
        _invoke(Atspi, ctrl)
        return
    if _is_wayland_session():
        warnings.warn(
            "click_control(invoke=False) needs screen coordinates, which don't work "
            "reliably on Wayland; falling back to invoke=True (the AT-SPI action) instead.",
            stacklevel=2,
        )
        _invoke(Atspi, ctrl)
        return
    _click_at_extents(Atspi, ctrl, button, double)


def double_click_control(window, control=None, backend: str = "atspi", timeout: float = 10):
    """Double click a control. See click_control."""
    click_control(window, control, double=True, backend=backend, timeout=timeout)


def right_click_control(window, control=None, backend: str = "atspi", timeout: float = 10):
    """Right click a control. See click_control."""
    click_control(window, control, button="right", backend=backend, timeout=timeout)


def type_in_control(window, control=None, text: str = "", literal: bool = True, pause: float = None,
                    backend: str = "atspi", timeout: float = 10):
    """Grab focus on a control and type text into it with simulated key presses.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict, optional): the control to type into. None types into the window.
        text (str): the text to type.
        literal (bool, optional): type the text as it is. If False the text uses
            pywinauto key syntax: {ENTER}, {TAB}, ^a (ctrl+a), %f (alt+f), +x (shift+x),
            translated to the keys2 hotkey syntax. Defaults to True.
        pause (float, optional): seconds between key presses. Defaults to None.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    Atspi = _prepare(backend)
    ctrl = get_control(window, control, backend, timeout)
    _grab_focus(Atspi, ctrl)
    if literal:
        write(text, interval=pause if pause is not None else 0.01)
    else:
        _send_key_syntax(text, pause or 0.0)


def set_control_text(window, control=None, text: str = "", backend: str = "atspi", timeout: float = 10):
    """Replace the text of an edit control directly, without typing.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict, optional): the edit control.
        text (str): the new text.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    Atspi = _prepare(backend)
    ctrl = get_control(window, control, backend, timeout)
    try:
        ok = ctrl.set_text_contents(text)
    except Exception:  # pylint: disable=broad-except
        ok = False
    if ok:
        return
    # EditableText not supported (or failed): fall back to select-all + type over it.
    _grab_focus(Atspi, ctrl)
    keys2("ctrl", "a")
    write(text)


def get_control_text(window, control=None, backend: str = "atspi", timeout: float = 10) -> str:
    """Read the text of a control. The text is also copied to the clipboard.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict, optional): the control. None reads the window title.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.

    Returns:
        str: the text of the control.
    """
    Atspi = _prepare(backend)
    ctrl = get_control(window, control, backend, timeout)
    text = None
    try:
        if ctrl.is_text():
            count = ctrl.get_character_count()
            text = Atspi.Text.get_text(ctrl, 0, count) if count else ""
    except Exception:  # pylint: disable=broad-except
        text = None
    if text is None:
        text = _safe_name(ctrl)
    copy(text)
    return text


def select_menu(window, path: str, backend: str = "atspi", timeout: float = 10):
    """Select a menu item.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        path (str): menu path separated by "->", e.g. "File->Save As..."
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the window. Defaults to 10.
    """
    Atspi = _prepare(backend)
    win = get_window(window, backend, timeout)
    names = [part.strip() for part in path.split("->")]
    node = win
    for i, name in enumerate(names):
        item = _find_menu_item(Atspi, node, name)
        if item is None:
            message = (
                f"Menu item not found: {name!r} (from path {path!r}) in window "
                f"{_safe_name(win)!r}. Closest names seen: {_collect_names(win) or '<none>'}"
            )
            if _has_no_children(win):
                message += " " + _QT_CHROME_ELECTRON_HINT
            raise LookupError(message)
        if i < len(names) - 1:
            _expand_menu(Atspi, item)  # best effort; GTK pre-populates the tree anyway
            node = item
        else:
            _invoke(Atspi, item)


def select_item(window, control, item, backend: str = "atspi", timeout: float = 10):
    """Select an item in a combo box, list box, list view or tab control.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict): the combo box / list control.
        item (str | int): text or index of the item.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    Atspi = _prepare(backend)
    ctrl = get_control(window, control, backend, timeout)

    # A GTK combo box's selectable items live inside a nested popup with role "menu";
    # other Selection-capable widgets (list, tabs) expose them directly as children -
    # see DONE.md section 1 findings.
    container = ctrl
    try:
        if ctrl.get_role() == Atspi.Role.COMBO_BOX and ctrl.get_child_count() == 1:
            popup = ctrl.get_child_at_index(0)
            if popup is not None:
                container = popup
    except Exception:  # pylint: disable=broad-except
        pass

    try:
        n = container.get_child_count()
    except Exception:  # pylint: disable=broad-except
        n = 0

    target = None
    if isinstance(item, int):
        if 0 <= item < n:
            try:
                target = container.get_child_at_index(item)
            except Exception:  # pylint: disable=broad-except
                target = None
    else:
        for i in range(n):
            try:
                child = container.get_child_at_index(i)
            except Exception:  # pylint: disable=broad-except
                continue
            if _safe_name(child) == item:
                target = child
                break

    if target is None:
        seen = [_safe_name(container.get_child_at_index(i)) for i in range(n)]
        raise LookupError(
            f"Item not found in {_safe_name(ctrl)!r} ({_safe_role_name(ctrl)}): {item!r}. "
            f"Items seen: {seen or '<none>'}"
        )

    # Clicking the item directly is what actually commits the selection for a GTK combo
    # box - Atspi.Selection.select_child() on the popup does not (section 1 finding).
    # Try that first; fall back to the Selection interface for widgets where it's correct.
    if _do_action_named(Atspi, target, ("click", "select")):
        return
    try:
        Atspi.Selection.select_child(container, target.get_index_in_parent())
    except Exception as err:  # pylint: disable=broad-except
        raise ValueError(
            f"Could not select {item!r} in {_safe_name(ctrl)!r}: no action to click it, "
            f"and the Selection interface failed ({err})."
        ) from err


def check_control(window, control, checked: bool = True, backend: str = "atspi", timeout: float = 10):
    """Check or uncheck a check box / toggle button.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict): the check box.
        checked (bool, optional): wanted state. Defaults to True.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    Atspi = _prepare(backend)
    ctrl = get_control(window, control, backend, timeout)
    try:
        is_checked = ctrl.get_state_set().contains(Atspi.StateType.CHECKED)
    except Exception as err:  # pylint: disable=broad-except
        raise ValueError(
            f"Could not read the checked state of {_safe_name(ctrl)!r} ({_safe_role_name(ctrl)}): {err}"
        ) from err
    if is_checked == checked:
        return
    if not _do_action_named(Atspi, ctrl, _TOGGLE_ACTION_NAMES):
        raise ValueError(
            f"{_safe_name(ctrl)!r} ({_safe_role_name(ctrl)}) has no AT-SPI action to toggle it."
        )


def uncheck_control(window, control, backend: str = "atspi", timeout: float = 10):
    """Uncheck a check box / toggle button. See check_control."""
    check_control(window, control, False, backend, timeout)


def wait_control(window, control=None, state: str = "exists visible",
                 backend: str = "atspi", timeout: float = 10):
    """Wait until a control reaches a state.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        control (str | dict, optional): the control. None waits for the window.
        state (str, optional): space separated: exists, visible, enabled, ready, active.
            Defaults to "exists visible".
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait. Defaults to 10.

    Raises:
        TimeoutError: if the state is not reached in time.
    """
    Atspi = _prepare(backend)
    words = state.split()
    if "ready" in words:
        words = words + ["visible", "enabled"]

    deadline = time.monotonic() + timeout
    last_err = None
    while True:
        try:
            ctrl = get_control(window, control, backend, 0)
        except LookupError as err:
            ctrl, last_err = None, err
        if ctrl is not None and _state_satisfied(Atspi, ctrl, words):
            return ctrl
        if time.monotonic() >= deadline:
            break
        time.sleep(0.2)

    raise TimeoutError(
        f"Control did not reach state {state!r} within {timeout}s"
        + (f" (last lookup error: {last_err})" if last_err else "")
    )


def control_exists(window, control=None, backend: str = "atspi", timeout: float = 0) -> bool:
    """Check if a window / control exists.

    Args:
        window (str): title of the window (regex).
        control (str | dict, optional): the control. None checks only the window.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to keep looking. Defaults to 0.

    Returns:
        bool: True if found.
    """
    _prepare(backend)
    try:
        get_control(window, control, backend, timeout)
    except LookupError:
        return False
    return True


def list_controls(window, depth: int = None, backend: str = "atspi", timeout: float = 10) -> str:
    """Print the controls of a window with the names usable as `control`.

    Args:
        window (str): title of the window (regex) or an Atspi.Accessible.
        depth (int, optional): how many levels deep to go. Defaults to all.
        backend (str, optional): "atspi". Defaults to "atspi".
        timeout (float, optional): seconds to wait for the window. Defaults to 10.

    Returns:
        str: the printed control tree.
    """
    Atspi = _prepare(backend)
    win = get_window(window, backend, timeout)
    lines = []

    def visit(node, indent):
        name = _safe_name(node)
        criteria = {}
        if name:
            criteria["title"] = name
        control_type = _role_to_control_type(Atspi, node)
        if control_type:
            criteria["control_type"] = control_type
        acc_id = _accessible_id(node)
        if acc_id:
            criteria["auto_id"] = acc_id
        lines.append(f"{'  ' * indent}{_safe_role_name(node)} {name!r} control={criteria!r}")
        if depth is not None and indent >= depth:
            return
        try:
            n = node.get_child_count()
        except Exception:  # pylint: disable=broad-except
            return
        for i in range(n):
            try:
                child = node.get_child_at_index(i)
            except Exception:  # pylint: disable=broad-except
                continue
            if child is not None:
                visit(child, indent + 1)

    visit(win, 0)
    if _has_no_children(win):
        lines.append(_QT_CHROME_ELECTRON_HINT)
    tree = "\n".join(lines)
    print(tree)
    return tree
