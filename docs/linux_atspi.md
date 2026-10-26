# Control actions on Linux (AT-SPI)

Design notes, findings and verification for the AT-SPI backend (`automonkey/atspi_funcs.py`).
The finished tasks themselves are in `tasklist.json` (group "Linux AT-SPI: ...", ids N1-N50);
this file keeps the background that used to sit between them in `DONE.md`.

_Collected from the earlier plan `pywinauto_for_linux.md` on 22.10.2026._

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

### Findings (spiked 2026-10-13, Debian 13 trixie / labwc / PyGObject 3.50 / AT-SPI 2.56)

- **Role names** (`Accessible.get_role_name()`) differ from the doc's draft guess — confirmed
  empirically, not from spec: push button → `"button"` (not `"push button"`), check box →
  `"check box"`, combo box → `"combo box"`, menu bar → `"menu bar"`, menu → `"menu"`, menu item →
  `"menu item"`, text entry → `"text"`. Section 3's mapping table should use these.
- **Invoke action name is `"click"` uniformly** for buttons, check boxes, and menu items — one
  action index (0) covers `click_control(invoke=True)`, `check_control`/`uncheck_control`, and
  `select_menu`.
- **`Atspi.Accessible.get_text(start, end)` is broken/deprecated in this PyGObject binding** —
  calling it as an instance method either raises `TypeError` or returns the `Accessible` object
  itself instead of a string, depending on call shape. Use the interface-style call instead:
  `Atspi.Text.get_text(accessible, start, end)`. `set_text_contents(string)` as an instance
  method works fine (`EditableText` interface).
- **Check box toggle**: `Atspi.Action.do_action(checkbox, 0)` flips `Atspi.StateType.CHECKED` as
  expected; read the state with `checkbox.get_state_set().contains(Atspi.StateType.CHECKED)`
  before deciding whether to act, to make `check_control`/`uncheck_control` idempotent.
- **Combo box selection gotcha**: a GTK combo box exposes its popup as a child with role
  `"menu"`, containing `"menu item"` children for each option, and the combo's own accessible
  `name` mirrors the current value. `Atspi.Selection.select_child()` on that popup does **not**
  commit the real GTK selection (combo's name stays unchanged). What works is calling
  `Atspi.Action.do_action(item, 0)` (`"click"`) directly on the target menu-item child — that
  both commits the selection and updates the combo's displayed name. `select_item` should walk
  to the matching item and click it, not use the `Selection` interface.
- **Menu item activation doesn't require first opening the menu** — calling `do_action` directly
  on a deeply nested menu item (e.g. `File → Save As...`) fires it immediately, no need to
  simulate opening each level first. Simplifies `select_menu`.
- Spike scripts used for all of the above are throwaway (not checked into the repo); the
  concrete findings above are what's load-bearing for section 2–4's implementation.

## 2. Backend structure

Verified (2026-10-13, this box): `import automonkey` picks `atspi_funcs` automatically on
Linux; `CONTROL_ACTIONS` unchanged; all 16 functions raise `NotImplementedError` cleanly when
called with a valid backend, and `ValueError` when called with `"uia"`/`"win32"`. Existing test
suite unaffected (`tests/test_pywinauto_funcs.py`'s one pre-existing Linux failure — no
`pywinauto` installed — reproduces identically on unmodified `main`; that's the section 6
skip-on-Linux gap, not something this phase introduced).

## 3. Finding windows and controls

**Bug caught and fixed while testing:** an unknown `control_type` in a dict is supposed to raise
`ValueError` (clear config-error signal), but the first version resolved the role lookup *inside*
the per-node predicate passed to `_find_all` - which wraps predicates in a broad `except Exception:
pass` to tolerate individual nodes misbehaving. That swallowed the `ValueError` and turned it into
a confusing `LookupError: Control not found`. Fixed by resolving `control_type` -> roles once in
`get_control`, before the search loop, so validation errors propagate instead of being treated as
"this one node didn't match."

Verified against the phase-1 hand-written GTK3 test app (still running, same box): `get_window`
by regex, `get_control` by dict (`title`+`control_type`, `control_type` alone, `title_re`,
`auto_id` falling back to name, `found_index`) and by string (exact, name+suffix, substring) all
return the expected node; an unknown `control_type` raises `ValueError`; a genuinely missing
control raises `LookupError` listing the real control names present. Confirmed the phase-4 stub
functions (e.g. `click_control`) now resolve the real control via `get_control` and only then hit
their `NotImplementedError` - i.e. phase 3 is already load-bearing for phase 4 without any changes
to those stub bodies.

## 4. Actions

**Real bug caught and fixed while testing (not AT-SPI specific):** `utils.copy()` (shared by
both backends' `get_control_text`) called two clipboard backends unconditionally - if either
raised, the whole call crashed, losing the control value that had already been successfully
read. It did raise here: pyperclip's auto-detected "gtk" backend does a legacy `import gtk`,
which PyGObject's compatibility shim turns into an `AttributeError` (not `ImportError`, so
pyperclip's own guard doesn't catch it) once anything has already done `from gi.repository
import X` in-process - which `atspi_funcs.py` always does. Fixed by making `copy()` try each
backend independently and swallow a failing one, so a dead clipboard backend can no longer
crash an unrelated control-read/write action, on either platform.

**Confirmed empirically, not assumed (2026-10-13, this box, a fresh GTK3 test app instance):**
- `click_control(invoke=True)`, `check_control`/`uncheck_control`, `set_control_text`/
  `get_control_text`, `select_item` (by text and by index), and `select_menu` all work exactly
  as implemented, verified by reading back real widget state after each call (checkbox
  `CHECKED` state, combo box display name, status label text) - not just "no exception raised."
- **The Wayland mouse/keyboard limitation is real and was isolated precisely**: the same test
  app launched natively (`GDK_BACKEND` unset, true Wayland) silently fails to receive
  `type_in_control`'s literal keystrokes - pyautogui's XTest-based injection can only reach
  Xwayland clients, never a native-Wayland surface, so the keys go nowhere. Relaunching the
  *identical* app with `GDK_BACKEND=x11` (forcing it through Xwayland) made `type_in_control`
  and a direct `_click_at_extents()` call (bypassing the session-wide Wayland guard on purpose,
  to test the mechanism itself) both work correctly - confirmed via the entry's text and the
  check box's `CHECKED` state actually changing. This is the same root cause as the documented
  "mouse clicks ... do not work" limit, now shown to apply to keyboard injection too, and
  confirmed to be about the client's backend (Xwayland vs native-Wayland), not about which
  compositor/session is running.
- `double_click_control`/`right_click_control` go through the same fallback-and-warn path on a
  Wayland session (verified: both raised the expected `UserWarning` and completed without error).
- `start_app` found a freshly launched `zenity` dialog by matching its PID against
  `Atspi.get_desktop(0)`'s applications.
- Full test suite still shows only the pre-existing, unrelated `test_pywinauto_funcs.py` failure
  (no `pywinauto` on Linux - the section 6 skip-on-Linux gap).

## 5. Environment handling

Verified (2026-10-13, this box): reproduced the bus-abort scenario in an isolated subprocess
to confirm the fatal-abort behavior is real (not theoretical) before designing around it;
confirmed the fix raises a clean, catchable `ConnectionError` instead, with the process
staying alive; confirmed normal operation (healthy bus) is unaffected; confirmed the
toolkit-accessibility warning fires with the exact expected text when the gsetting is
temporarily flipped to `false` (and restored it afterward); confirmed the Qt/Chrome/Electron
hint appears for a genuinely childless GTK window (`get_control`, `select_menu`,
`list_controls` all show it) and does *not* appear for the normal GTK test app (which has
children). `_default_display_env` confirmed to set the exact right value when
`DBUS_SESSION_BUS_ADDRESS` is unset. Full test suite still shows only the pre-existing,
unrelated `test_pywinauto_funcs.py` failure.

## 6. Tests

Verified (2026-10-13, this box): all 31 new unit tests pass; full suite went from
**1 failed, 16 passed, 1 skipped** (start of this phase) to **38 passed, 13 skipped, 0
failed**. Confirmed the integration tests correctly skip by default and also correctly
skip (not error) with `AUTOMONKEY_ATSPI_INTEGRATION=1` set but the target apps absent.
`.github/workflows/python-package.yml` parses as valid YAML with the expected step order.

## 7. Packaging and docs

Verified (2026-10-13, this box): `setup.py` still compiles; the new MCP `list_controls`
tool imports, registers, and returns a real control tree when called against a live
window; full test suite unaffected (38 passed, 13 skipped, 0 failed, same as end of
section 6).

## Final review: running the integration tests for real

`gnome-calculator` and `gnome-text-editor` got installed on this box after section 6, so
`tests/test_atspi_integration.py` could finally run for real instead of only by analogy
to `mousepad`. Both tests initially failed - not because the AT-SPI logic was wrong, but
because they exercised three more real, previously-undiscovered issues:

- **`start_app` could make a caller's own script appear to hang.** `subprocess.Popen(args)`
  didn't redirect the spawned app's stdin/stdout/stderr or detach its session, so the
  spawned (possibly long-running, GUI) process kept the caller's own stdout pipe open.
  Reproduced directly: a script that launched `gnome-calculator` and then just printed
  text would "hang" from the outside (nothing ever reads EOF) even though every line it
  printed had already run. **Fixed**: `stdin/stdout/stderr=subprocess.DEVNULL,
  start_new_session=True`.
- **Rapid-fire `do_action` calls can outrun the app.** `Atspi.Action.do_action()` returns
  once the D-Bus call completes, not once the target app has processed the resulting GTK
  signal. Clicking gnome-calculator's "5", "+", "3" with no delay between them dropped
  "3" entirely (display read back "5+", not "5+3") - confirmed by adding a ~0.3s sleep
  between clicks, which fixed it every time. This wasn't a bug in `click_control`/
  `_invoke`/`_do_action_named` themselves (each call did exactly what it should); it's an
  inherent async-timing property of AT-SPI actions against a live app, so the fix belongs
  in the caller (the integration test now sleeps between clicks), not the library -
  forcing an unconditional delay into every `click_control` call would be the wrong
  tradeoff for callers that don't need it.
- **`Component.grab_focus()` fails app-wide on `gnome-text-editor` (GTK4)** - confirmed
  on a plain button too, not just the text widget, so it's a toolkit/app-level AT-SPI
  gap, not something wrong with how we were calling it. Previously `_grab_focus` treated
  any `grab_focus()` failure as fatal. **Fixed**: fall back to a real mouse click on the
  control's extents (the same mechanism `click_control(invoke=False)` already uses) to
  establish focus the way a real user would - works wherever mouse clicks do (X11/
  Xwayland; same Wayland caveat as everywhere else). Confirmed the fallback is what
  actually made `type_in_control`/`set_control_text` work against this app.
- Also hit, while debugging, the **exact Wayland keyboard-injection limitation already
  documented in sections 4/6** a third time: `gnome-text-editor` launched natively
  (Wayland) never received `type_in_control`'s keystrokes at all; the identical app
  forced through Xwayland (`GDK_BACKEND=x11`) worked immediately, `_grab_focus` fallback
  included. Not a new finding, but a third independent confirmation of the same root
  cause (pyautogui/XTest can only reach Xwayland clients) - the integration test passes
  as written because CI runs it under `xvfb` (a real X11 server, not Wayland at all), so
  this distinction doesn't apply there; it only shows up when running these tests by hand
  on a native-Wayland desktop like this one.
- Minor test-hygiene fix alongside these: `_stop()`'s plain `kill` occasionally wasn't
  enough to make `gnome-calculator` actually exit before the next test started - added a
  SIGKILL fallback after a short wait.

Verified (2026-10-13, this box, real `gnome-calculator`/`gnome-text-editor`): both
integration tests pass (`GDK_BACKEND=x11`, matching what CI's `xvfb` provides
automatically); full suite still 38 passed, 13 skipped, 0 failed; no leftover GUI
processes after a run.
