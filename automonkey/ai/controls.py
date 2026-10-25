"""The accessibility tree, for AI agents: what controls a window has, where they are
(in screenshot coordinates), which one has the keyboard focus.

Testing through the tree is how an agent can be *complete*: list every menu item,
button and link of a window, then click each one with the real mouse. Coordinates
are image pixels of the latest screenshot, like everywhere else in the AI layer.

Windows only for now (UI Automation through pywinauto). Apps expose a tree when their
toolkit supports it: Win32, WinForms, WPF, WinUI, Qt, Flutter, Electron/Chromium, and
egui with AccessKit (eframe's default). DearPyGui and other canvas-drawn UIs expose
nothing; use OCR (`find_text`) and screenshots for them.
"""
from __future__ import annotations

import ctypes
import sys
import unicodedata

from . import screen, windows

# Control types worth listing when the agent asks for "what can I click?".
INTERACTIVE = {"Button", "MenuItem", "Hyperlink", "CheckBox", "RadioButton", "ComboBox", "Edit",
               "ListItem", "TabItem", "TreeItem", "Slider", "Spinner", "SplitButton", "MenuBar",
               "Menu", "DataItem", "Document", "ScrollBar", "Thumb", "HeaderItem"}


# Typographic characters apps use in labels ("Don’t save", “Open…”) and the plain ones
# an agent types.
_PLAIN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2026": "...",
                        "\u2013": "-", "\u2014": "-", "\u00a0": " ", "&": None})


def normalize(name: str) -> str:
    """Lower-case, plain-ASCII punctuation, accents removed (OCR confuses e-diaeresis,
    e-acute and e-grave), mnemonic '&' removed, spaces collapsed."""
    text = unicodedata.normalize("NFKD", name.translate(_PLAIN))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def _require_windows():
    if sys.platform != "win32":
        raise RuntimeError("the accessibility helpers of the AI layer are implemented on Windows only; "
                           "on Linux use automonkey.list_controls (AT-SPI)")


def _root(window: str | int):
    from pywinauto.uia_element_info import UIAElementInfo
    w = windows.find_window(window)
    return w, UIAElementInfo(w["id"])


def _props(ei) -> dict:
    """Cheap, exception-safe snapshot of one element."""
    def get(attr, default=None):
        try:
            return getattr(ei, attr)
        except Exception:
            return default
    r = get("rectangle")
    rect = None
    if r is not None and r.right > r.left and r.bottom > r.top:
        v = screen.view()
        x0, y0 = v.to_image(r.left, r.top)
        x1, y1 = v.to_image(r.right, r.bottom)
        rect = (x0, y0, x1 - x0, y1 - y0)
    return dict(type=get("control_type", "") or "", name=(get("name", "") or "").strip(),
                auto_id=get("automation_id", "") or "", enabled=get("enabled", True), rect=rect)


def _toggle(ei) -> str:
    try:
        from pywinauto.controls.uiawrapper import UIAWrapper
        state = UIAWrapper(ei).get_toggle_state()
        return {0: "off", 1: "on", 2: "mixed"}.get(state, "")
    except Exception:
        return ""


def describe(p: dict, toggle: str = "") -> str:
    parts = [p["type"] or "?"]
    if p["name"]:
        parts.append(repr(p["name"]))
    if p["auto_id"]:
        parts.append(f"id={p['auto_id']}")
    if p["rect"]:
        x, y, w, h = p["rect"]
        parts.append(f"click {x + w // 2},{y + h // 2} (box {x},{y} {w}x{h})")
    else:
        parts.append("(no box: off screen or hidden)")
    if not p["enabled"]:
        parts.append("DISABLED")
    if toggle:
        parts.append(f"toggle={toggle}")
    return " ".join(parts)


def _popups(w: dict) -> list:
    """Top-level popups the window's process shows outside its own tree: Win32 and WinUI
    menus, dropdown lists, flyouts and owned dialogs. Qt and egui put open menus inside
    the window's tree, other toolkits make them separate top-level windows."""
    from pywinauto.uia_element_info import UIAElementInfo
    found = []
    try:
        tops = UIAElementInfo().children()
    except Exception:
        return found
    for top in tops:
        try:
            if top.process_id != w["pid"] or not top.handle or top.handle == w["id"]:
                continue
            owned = windows._root(top.handle) == windows._root(w["id"])
            style = ctypes.windll.user32.GetWindowLongW(top.handle, -16) & 0xFFFFFFFF  # GWL_STYLE
            popup = style & 0x80000000 and not style & 0x00C00000  # WS_POPUP without WS_CAPTION
            if owned or popup or top.control_type in ("Menu", "List", "ToolTip"):
                found.append(top)
        except Exception:
            continue
    return found


def walk(window: str | int, depth: int | None = None, interactive_only: bool = False):
    """Yield (level, element_info, props) for every element of the window and of its open
    popups (menus, dropdowns), depth first."""
    _require_windows()
    w, root = _root(window)
    stack = [(0, root)] + [(1, p) for p in reversed(_popups(w))]
    while stack:
        level, ei = stack.pop()
        p = _props(ei)
        if level and (not interactive_only or p["type"] in INTERACTIVE):
            yield level, ei, p
        if depth is None or level < depth:
            try:
                kids = ei.children()
            except Exception:
                kids = []
            stack.extend((level + 1, k) for k in reversed(kids))


def tree(window: str | int, depth: int | None = None, interactive_only: bool = False,
         max_items: int = 400) -> str:
    """Compact, indented control list with click points in screenshot coordinates."""
    w, _root_ei = _root(window)
    lines = [f"window {w['title']!r} [{w['wm_class']}]"]
    for n, (level, ei, p) in enumerate(walk(window, depth, interactive_only)):
        if n >= max_items:
            lines.append(f"... more than {max_items} controls; pass a smaller depth or interactive_only")
            break
        toggle = _toggle(ei) if p["type"] in ("CheckBox", "Button", "RadioButton", "MenuItem") else ""
        lines.append("  " * level + describe(p, toggle))
    if len(lines) == 1:
        lines.append("  (no accessible controls: the app draws its own UI without an accessibility tree; "
                     "use OCR and screenshots)")
    return "\n".join(lines)


def find(window: str | int, name: str, control_type: str | None = None) -> dict:
    """The control whose name matches `name` (exact, else case-insensitive substring),
    optionally of `control_type`. Visible, enabled matches win."""
    _require_windows()
    want = normalize(name)
    exact, partial = [], []
    for _level, ei, p in walk(window):
        if control_type and p["type"].lower() != control_type.lower():
            continue
        nm = normalize(p["name"])
        # The visible text before a tab is the label; after it comes the shortcut ("Select All\tCtrl+A").
        label = normalize(p["name"].split("\t")[0])
        auto_id = p["auto_id"].lower()
        # Qt reports objectName paths ("...splitter.QWidget.nameEdit"): match the last part too.
        if want in (nm, label) or auto_id == name.strip().lower() or auto_id.endswith("." + name.strip().lower()):
            exact.append(p)
        elif want and want in nm:
            partial.append(p)
    for group in (exact, partial):
        group.sort(key=lambda p: (p["rect"] is None, not p["enabled"]))
        if group:
            return group[0]
    kind = f" {control_type}" if control_type else ""
    raise LookupError(f"no{kind} control named {name!r} in window {window!r} (see `controls`)")


TEXTUAL = {"Text", "Button", "CheckBox", "RadioButton", "MenuItem", "TabItem", "ListItem", "HeaderItem",
           "Hyperlink", "TreeItem", "DataItem", "SplitButton"}


def clipped(window: str | int, max_items: int = 120) -> list[str]:
    """Labels whose visible text is cut off: the control's full name (from the
    accessibility tree) is compared with what OCR reads inside its box on screen. A
    clear, shorter prefix (or an ellipsis) means the text is clipped or elided.
    Controls whose name isn't their visible text (icon buttons) never match a prefix,
    so they are skipped rather than reported."""
    from . import ocr
    img = screen.grab()
    s = 1 / screen.view().scale
    found, checked = [], 0
    for _level, _ei, p in walk(window):
        if p["type"] not in TEXTUAL or not p["rect"] or len(normalize(p["name"])) < 6:
            continue
        checked += 1
        if checked > max_items:
            break
        x, y, w, h = p["rect"]
        crop = img.crop((round(x * s), round(y * s), round((x + w) * s), round((y + h) * s)))
        seen = normalize(ocr.read_image(crop))  # normalize() also folds line breaks
        full = normalize(p["name"])
        elided = seen.endswith("...") or seen.endswith("..")
        core = seen.rstrip(". ")
        if len(core) < 3 or not full.startswith(core[:max(3, len(core) - 2)]):
            continue
        if elided or len(core) < 0.85 * len(full):
            found.append(f"{describe(p)} shows only {seen!r}")
    return found


def focused() -> dict:
    """The element that has the keyboard focus, anywhere on the desktop."""
    _require_windows()
    from pywinauto.uia_defines import IUIA
    from pywinauto.uia_element_info import UIAElementInfo
    return _props(UIAElementInfo(IUIA().iuia.GetFocusedElement()))
