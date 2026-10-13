# Control actions on Linux (AT-SPI)

Goal: the control actions from `automonkey/pywinauto_funcs.py` (`click_control`, `type_in_control`, ...)
work on Linux with the same names and arguments, so a `chain` script runs on both systems.

Linux equivalent of the Windows accessibility tree: **AT-SPI**, used through `gi.repository.Atspi` (PyGObject).
pywinauto itself has no released Linux backend, so we write our own thin layer.

Known limits:
- Apps must expose accessibility (GTK, GNOME, LibreOffice, Firefox: yes; Qt: needs `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1`;
  Chrome/Electron: needs `--force-renderer-accessibility`; self-drawn UIs: no).
- Wayland: tree reading and AT-SPI actions work; screen coordinates, mouse clicks on controls and raising windows do not.
- PyGObject usually comes from the distro (`python3-gi`, `gir1.2-atspi-2.0`), not from pip.

## 1. Research and setup

- [ ] Set up a Linux test machine/VM with GNOME on both X11 and Wayland sessions
- [ ] Install `python3-gi`, `gir1.2-atspi-2.0`, `at-spi2-core`; check `gsettings get org.gnome.desktop.interface toolkit-accessibility`
- [ ] Spike: list top-level windows and dump the tree of gnome-text-editor, gnome-calculator, LibreOffice Writer, Firefox
- [ ] Spike: press a button, set text, read text, toggle a check box, select a combo item, open a menu via AT-SPI
- [ ] Note which of these work on Wayland vs X11
- [ ] Decide the minimum supported distros / PyGObject version
- [ ] Look at pywinauto's unreleased `atspi` backend and dogtail for edge cases (do not depend on them)

## 2. Backend structure

- [ ] Create `automonkey/atspi_funcs.py` with the same public functions and signatures as `pywinauto_funcs.py`
- [ ] Lazy import of `gi` / `Atspi` with an error that names the distro packages to install
- [ ] Choose the backend by platform in `automonkey/automonkey.py` (win32 -> pywinauto_funcs, linux -> atspi_funcs);
      keep the import lines and `CONTROL_ACTIONS` unchanged so `chain` needs no changes
- [ ] Accept `backend="atspi"` (default on Linux); raise a clear error for `"uia"` / `"win32"` on Linux and vice versa
- [ ] macOS: keep the functions importable and raise `NotImplementedError` when used

## 3. Finding windows and controls

- [ ] `get_window`: find the top-level window by title regex (`.*?{title}.*?`, same as Windows) across all applications
- [ ] Wait with `timeout` until the window exists and is `SHOWING` / `VISIBLE`; return the first match
- [ ] `get_control` with dict criteria; map keys:
  - [ ] `title` -> accessible name, `title_re` -> name regex
  - [ ] `control_type` -> role (map pywinauto names: Button -> push button, Edit -> text/entry, Document -> document text,
        CheckBox -> check box, ComboBox -> combo box, MenuItem -> menu item, List -> list, ...)
  - [ ] `auto_id` -> accessible id (AT-SPI 2.34+) or `id` attribute; fall back to name
  - [ ] `found_index` for several matches
- [ ] `get_control` with a string ("best match"): exact name, then name + role suffix (`"SaveButton"`), then case-insensitive substring
- [ ] Limit tree search depth / skip huge subtrees (browsers) to keep lookups fast
- [ ] Clear error when nothing matches: list the closest names found

## 4. Actions

- [ ] `click_control(invoke=True)`: run the control's "click" / "press" / "activate" action
- [ ] `click_control(invoke=False)`: mouse click at the control's screen extents (X11); on Wayland fall back to the action and warn
- [ ] `double_click_control`, `right_click_control` (mouse based; document Wayland limits)
- [ ] `type_in_control`: grab focus (`Component.grab_focus`), then type with the existing layout-aware `write`;
      `literal=False` -> translate pywinauto key syntax (`{ENTER}`, `^a`, `%f`, `+x`) to `keys2`
- [ ] `type_in_control(pause=...)`: delay between key presses
- [ ] `set_control_text`: `EditableText.set_text_contents`; fall back to select all + type
- [ ] `get_control_text`: `Text` interface for editable text, else accessible name; copy to clipboard like on Windows
- [ ] `select_menu("File->Save As...")`: walk menu items by name, expand each level, activate the last one
- [ ] `select_item`: `Selection` interface by text or index (combo box, list, tabs)
- [ ] `check_control` / `uncheck_control`: read `CHECKED` state, run the toggle action only if needed
- [ ] `wait_control(state=...)`: map `exists`, `visible` (`SHOWING`), `enabled` (`ENABLED`/`SENSITIVE`), `ready`, `active` (`ACTIVE`/`FOCUSED`)
- [ ] `control_exists`
- [ ] `list_controls(depth=...)`: print role, name, id and the dict to use as `control`; return the text
- [ ] `start_app`: start the process and wait until its application appears on the AT-SPI bus

## 5. Environment handling

- [ ] Detect a missing AT-SPI bus / disabled accessibility and print how to enable it
- [ ] Extend `_default_display_env` in `automonkey/__init__.py` with `DBUS_SESSION_BUS_ADDRESS` when started from a service / MCP client
- [ ] Document the Qt / Chrome / Electron flags in the error message when an app shows an empty tree

## 6. Tests

- [ ] Unit tests with fake accessibles for: criteria mapping, best match, menu walk, check toggle, text fallback, key syntax translation
- [ ] Make the existing `tests/test_pywinauto_funcs.py` skip on Linux and the new tests skip on Windows
- [ ] Integration tests (opt-in via env var) against gnome-calculator and gnome-text-editor
- [ ] CI: install `python3-gi gir1.2-atspi-2.0 at-spi2-core xvfb`, run the integration tests under Xvfb + `dbus-run-session`
- [ ] Enable the commented-out pytest step in `.github/workflows/python-package.yml`

## 7. Packaging and docs

- [ ] `setup.py`: add a `linux` extra (or document that PyGObject comes from the distro); keep `pywinauto` Windows-only
- [ ] README section 6: add Linux setup, the criteria mapping table and the Wayland limits
- [ ] Add the Linux version of the Calculator / text editor examples to the README
- [ ] Optional: expose the control tree to the MCP server (`automonkey/ai/mcp_server.py`) on both systems
- [ ] Update `HISTORY.rst` and bump the version
