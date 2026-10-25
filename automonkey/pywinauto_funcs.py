"""Control-level Windows automation based on pywinauto.

Unlike the mouse/image functions, these find controls (buttons, edits, menus, ...)
through the accessibility tree, so they do not depend on screen resolution,
theme or window position.

Every function takes:
    window: title of the top-level window (regex, matched anywhere in the title,
        like focus/close/minimize) or a pywinauto window object.
    control: what to act on inside the window:
        - None: the window itself
        - str: pywinauto "best match" name, e.g. "Save", "SaveButton", "Edit"
        - dict: pywinauto search criteria, e.g. {"title": "Save", "control_type": "Button"}
    backend: "uia" (default, modern apps) or "win32" (old MFC/WinForms apps).
    timeout: seconds to wait for the window/control to appear.

Use list_controls(window) to see the names of the controls in a window.
pywinauto is only available on Windows: pip install pywinauto
"""
from io import StringIO
from contextlib import redirect_stdout

from .utils import copy

_TYPE_KEYS_SPECIAL = "{}+^%~()"

_VALID_BACKENDS = ("uia", "win32", None)


def _check_backend(backend: str):
    if backend not in _VALID_BACKENDS:
        raise ValueError(
            f"backend={backend!r} is not valid on Windows. Use backend='uia' (the default) "
            "or 'win32' here; 'atspi' is the Linux backend (automonkey/atspi_funcs.py)."
        )


def _pywinauto():
    try:
        import pywinauto  # pylint: disable=import-outside-toplevel
    except ImportError as err:
        raise ImportError(
            "This function needs pywinauto (Windows only): pip install pywinauto"
        ) from err
    return pywinauto


def get_window(window, backend: str = "uia", timeout: float = 10):
    """Find a top-level window and wait until it is visible.

    Args:
        window (str): title of the window, regex matched anywhere in the title.
            A pywinauto window object is returned as it is.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the window. Defaults to 10.

    Returns:
        pywinauto WindowSpecification, for anything not covered by these functions.

    Raises:
        pywinauto.timings.TimeoutError: no such window appeared in time. The message
            names the open windows, since the usual cause is that the app isn't running
            (start it first, e.g. with start_app) or its title is different.
    """
    _check_backend(backend)
    if not isinstance(window, str):
        return window
    pywinauto = _pywinauto()
    desktop = pywinauto.Desktop(backend=backend)
    spec = desktop.window(title_re=f".*?{window}.*?", found_index=0)
    try:
        spec.wait("exists visible", timeout=timeout)
    except pywinauto.timings.TimeoutError as err:
        try:
            titles = [t for t in (w.window_text() for w in desktop.windows()) if t]
        except Exception:  # listing is only a hint for the message
            titles = []
        raise pywinauto.timings.TimeoutError(
            f"no visible window with a title matching {window!r} after {timeout}s - is the app "
            f"running? Open windows: {'; '.join(titles[:25]) or 'none'}") from err
    return spec


def _control_spec(win, control):
    if control is None:
        return win
    if isinstance(control, dict):
        return win.child_window(**control)
    return win.child_window(best_match=control)


def get_control(window, control=None, backend: str = "uia", timeout: float = 10):
    """Find a control inside a window and wait until it exists.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict, optional): best-match name or search criteria.
            None returns the window itself.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait. Defaults to 10.

    Returns:
        pywinauto control wrapper
    """
    return _control_spec(get_window(window, backend, timeout), control).wait("exists", timeout=timeout)


def start_app(command: str, backend: str = "uia", timeout: float = 10):
    """Start an application with pywinauto.

    Args:
        command (str): command line / path of the executable, e.g. "notepad.exe"
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the app to be ready. Defaults to 10.

    Returns:
        pywinauto Application
    """
    _check_backend(backend)
    return _pywinauto().Application(backend=backend).start(command, timeout=timeout)


def click_control(window, control=None, button: str = "left", double: bool = False,
                  invoke: bool = False, backend: str = "uia", timeout: float = 10):
    """Click a control.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict, optional): the control to click. None clicks the window.
        button (str, optional): "left", "right" or "middle". Defaults to "left".
        double (bool, optional): double click. Defaults to False.
        invoke (bool, optional): press the control through the accessibility API
            instead of moving the mouse. Works for buttons/menu items even when
            the window is covered. Defaults to False.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    ctrl = get_control(window, control, backend, timeout)
    if invoke:
        if hasattr(ctrl, "invoke"):
            ctrl.invoke()
        else:
            ctrl.click()
        return
    ctrl.click_input(button=button, double=double)


def double_click_control(window, control=None, backend: str = "uia", timeout: float = 10):
    """Double click a control. See click_control."""
    click_control(window, control, double=True, backend=backend, timeout=timeout)


def right_click_control(window, control=None, backend: str = "uia", timeout: float = 10):
    """Right click a control. See click_control."""
    click_control(window, control, button="right", backend=backend, timeout=timeout)


def _escape_keys(text: str) -> str:
    return "".join(f"{{{char}}}" if char in _TYPE_KEYS_SPECIAL else char for char in text)


def type_in_control(window, control=None, text: str = "", literal: bool = True, pause: float = None,
                    backend: str = "uia", timeout: float = 10):
    """Focus a control and type text into it with simulated key presses.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict, optional): the control to type into. None types into the window.
        text (str): the text to type.
        literal (bool, optional): type the text as it is. If False the text uses
            pywinauto key syntax: {ENTER}, {TAB}, ^a (ctrl+a), %f (alt+f), +x (shift+x).
            Defaults to True.
        pause (float, optional): seconds between key presses. Increase it if a slow
            or just started app loses characters. Defaults to pywinauto's 0.01.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    ctrl = get_control(window, control, backend, timeout)
    keys = _escape_keys(text) if literal else text
    ctrl.type_keys(keys, pause=pause, with_spaces=True, with_tabs=True, with_newlines=True, set_foreground=True)


def set_control_text(window, control=None, text: str = "", backend: str = "uia", timeout: float = 10):
    """Replace the text of an edit control directly, without typing.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict, optional): the edit control.
        text (str): the new text.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    ctrl = get_control(window, control, backend, timeout)
    if hasattr(ctrl, "set_edit_text"):
        ctrl.set_edit_text(text)
    else:  # generic uia control, e.g. a Document: use the Value pattern
        ctrl.iface_value.SetValue(text)


def get_control_text(window, control=None, backend: str = "uia", timeout: float = 10) -> str:
    """Read the text of a control. The text is also copied to the clipboard.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict, optional): the control. None reads the window title.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.

    Returns:
        str: the text of the control
    """
    ctrl = get_control(window, control, backend, timeout)
    text = None
    if hasattr(ctrl, "get_value"):  # uia edits: window_text() is only the label
        try:
            text = ctrl.get_value()
        except Exception:  # pylint: disable=broad-except
            text = None  # control has no Value pattern
    if text is None:
        texts = [_ for _ in ctrl.texts() if _]
        text = "\n".join(texts) if texts else ctrl.window_text()
    copy(text)
    return text


def select_menu(window, path: str, backend: str = "uia", timeout: float = 10):
    """Select a menu item.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        path (str): menu path separated by "->", e.g. "File->Save As..."
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the window. Defaults to 10.
    """
    win = get_control(window, None, backend, timeout)
    try:
        win.menu_select(path)
    except AttributeError:  # uia finds only a menu bar that is a direct child of the window
        _walk_menu(win, path, timeout)


def _find_menu_item(win, name: str):
    for item in win.descendants(control_type="MenuItem"):
        if item.window_text().replace("&", "").strip().lower() == name.lower():
            return item
    raise LookupError(f"Menu item not found: {name}")


def _walk_menu(win, path: str, timeout: float):
    """Open each menu of the path in turn; submenus show up as descendants of the window"""
    wait_until_passes = _pywinauto().timings.wait_until_passes
    names = [_.strip() for _ in path.split("->")]
    for i, name in enumerate(names):
        item = wait_until_passes(timeout, 0.1, _find_menu_item, LookupError, win, name)
        try:
            if i == len(names) - 1:
                item.invoke()
            else:
                item.expand()
        except Exception:  # pylint: disable=broad-except
            item.click_input()  # item without Invoke / ExpandCollapse pattern


def select_item(window, control, item, backend: str = "uia", timeout: float = 10):
    """Select an item in a combo box, list box, list view or tab control.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict): the combo box / list control.
        item (str | int): text or index of the item.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    get_control(window, control, backend, timeout).select(item)


def check_control(window, control, checked: bool = True, backend: str = "uia", timeout: float = 10):
    """Check or uncheck a check box / toggle button.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict): the check box.
        checked (bool, optional): wanted state. Defaults to True.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the control. Defaults to 10.
    """
    ctrl = get_control(window, control, backend, timeout)
    if hasattr(ctrl, "get_toggle_state"):  # uia
        if bool(ctrl.get_toggle_state()) != checked:
            ctrl.toggle()
    elif checked:
        ctrl.check()
    else:
        ctrl.uncheck()


def uncheck_control(window, control, backend: str = "uia", timeout: float = 10):
    """Uncheck a check box / toggle button. See check_control."""
    check_control(window, control, False, backend, timeout)


def wait_control(window, control=None, state: str = "exists visible",
                 backend: str = "uia", timeout: float = 10):
    """Wait until a control reaches a state.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        control (str | dict, optional): the control. None waits for the window.
        state (str, optional): space separated: exists, visible, enabled, ready, active.
            Defaults to "exists visible".
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait. Defaults to 10.

    Raises:
        pywinauto.timings.TimeoutError: if the state is not reached in time.
    """
    return _control_spec(get_window(window, backend, timeout), control).wait(state, timeout=timeout)


def control_exists(window, control=None, backend: str = "uia", timeout: float = 0) -> bool:
    """Check if a window / control exists.

    Args:
        window (str): title of the window (regex).
        control (str | dict, optional): the control. None checks only the window.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to keep looking. Defaults to 0.

    Returns:
        bool: True if found
    """
    pywinauto = _pywinauto()
    try:
        get_control(window, control, backend, timeout)
    except (pywinauto.timings.TimeoutError, pywinauto.findwindows.ElementNotFoundError):
        return False
    return True


def list_controls(window, depth: int = None, backend: str = "uia", timeout: float = 10) -> str:
    """Print the controls of a window with the names usable as `control`.

    Args:
        window (str): title of the window (regex) or a pywinauto window object.
        depth (int, optional): how many levels deep to go. Defaults to all.
        backend (str, optional): "uia" or "win32". Defaults to "uia".
        timeout (float, optional): seconds to wait for the window. Defaults to 10.

    Returns:
        str: the printed control tree
    """
    win = get_window(window, backend, timeout)
    out = StringIO()
    with redirect_stdout(out):
        win.print_control_identifiers(depth=depth)
    tree = out.getvalue()
    print(tree)
    return tree

