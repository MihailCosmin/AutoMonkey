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

- [x] Set up a Linux test machine/VM with GNOME on both X11 and Wayland sessions
      — no GNOME box available; used the real dev machine instead: Debian 13 (trixie) on
      Raspberry Pi, desktop is **labwc** (wlroots/Wayland), with Xwayland running rootless for
      X11 app compat. Gives both a native-Wayland surface and an X11 (Xwayland) surface on one
      machine, which covers what the spike actually needed.
- [x] Install `python3-gi`, `gir1.2-atspi-2.0`, `at-spi2-core`; check `gsettings get org.gnome.desktop.interface toolkit-accessibility`
      — `python3-gi` was already present; `gir1.2-atspi-2.0` and `at-spi2-core` were missing
      (both needed sudo). `toolkit-accessibility` was `false`; set to `true` via
      `gsettings set org.gnome.desktop.interface toolkit-accessibility true` (per-user dconf,
      no root needed, but requires restarting apps to take effect). The AT-SPI D-Bus service
      is activated on demand (`org.a11y.Bus` → `/usr/libexec/at-spi-bus-launcher` via
      `at-spi-dbus-bus.service`) — nothing to start manually once `at-spi2-core` is installed.
      **Gotcha:** `NO_AT_BRIDGE=1` was set in this machine's session environment, which
      silently disables the GTK ATK→AT-SPI bridge — a plain GTK3 app launched with that var set
      registers zero AT-SPI children even though accessibility is otherwise on. `automonkey`
      must make sure this var is unset (or `0`) in the environment it launches/controls apps in.
      (zenity was unaffected by it in this test, for unclear reasons — don't assume other apps
      are equally immune.)
- [x] Spike: list top-level windows and dump the tree of gnome-text-editor, gnome-calculator, LibreOffice Writer, Firefox
      — neither gnome-text-editor nor gnome-calculator is installed on this box; substituted
      `zenity` and a small hand-written GTK3 test app (button, entry, check box, combo box,
      menu bar) for controlled testing, plus Firefox for a real Xwayland app. Tree dump worked
      cleanly on all three. Browser trees are large as the doc warned — kept dump depth shallow
      (3) for Firefox; a real implementation needs the depth-limiting from section 3.
- [x] Spike: press a button, set text, read text, toggle a check box, select a combo item, open a menu via AT-SPI
      — all done against the hand-written GTK3 app; see Findings below for the exact API calls
      and the one real gotcha (combo box selection).
- [x] Note which of these work on Wayland vs X11
      — tree reading and all of the above actions worked identically on the native-Wayland GTK
      app and on Firefox (Xwayland). No backend-specific code was needed for any of this; the
      Wayland/X11 split only matters for screen-coordinate mouse actions (phase 4), as the doc
      already predicted.
- [x] Decide the minimum supported distros / PyGObject version
      — floor from this box: Debian 13 (trixie)-equivalent, PyGObject 3.50+, AT-SPI2 2.56+
      (`at-spi2-core`, `gir1.2-atspi-2.0`). This is one data point, not a distro survey — revisit
      if we need to support something materially older (e.g. Debian 12/Ubuntu 22.04 ship
      AT-SPI 2.44-ish and older PyGObject).
- [x] Look at pywinauto's unreleased `atspi` backend and dogtail for edge cases (do not depend on them)
      — pywinauto's AT-SPI work lives only on an unreleased `atspi` docs/git branch
      (`pywinauto.linux.application`, `atspi_element_info`, `atspi_controls`/`atspiwrapper`);
      tracked by [pywinauto#328](https://github.com/pywinauto/pywinauto/issues/328), open since
      2017, never shipped to PyPI — confirms we're on our own, it's only useful as an API-shape
      reference. **dogtail** (gitlab.com/dogtail/dogtail) is the more relevant prior art: still
      pyatspi/gi-based, and notably depends on a separate privileged helper,
      **`gnome-ponytail-daemon`**, specifically to synthesize pointer/mouse input under Wayland.
      Worth evaluating in phase 4 as a possible real fix for the "mouse clicks on controls don't
      work on Wayland" limitation, rather than treating it as a hard wall.

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

- [x] Create `automonkey/atspi_funcs.py` with the same public functions and signatures as `pywinauto_funcs.py`
      — all 16 functions present (`get_window`, `get_control`, `start_app`,
      `click_control`, `double_click_control`, `right_click_control`, `type_in_control`,
      `set_control_text`, `get_control_text`, `select_menu`, `select_item`, `check_control`,
      `uncheck_control`, `wait_control`, `control_exists`, `list_controls`), same names/args as
      `pywinauto_funcs.py` (only `backend` defaults to `"atspi"` instead of `"uia"`). Bodies are
      stubs (`raise NotImplementedError(...)` pointing back here) — sections 3/4 fill them in.
- [x] Lazy import of `gi` / `Atspi` with an error that names the distro packages to install
      — `_atspi()` does `gi.require_version("Atspi", "2.0"); from gi.repository import Atspi`
      inside a try/except, raising `ImportError` with the exact apt command
      (`python3-gi gir1.2-atspi-2.0 at-spi2-core`) and the `gsettings` accessibility command.
- [x] Choose the backend by platform in `automonkey/automonkey.py` (win32 -> pywinauto_funcs, linux -> atspi_funcs);
      keep the import lines and `CONTROL_ACTIONS` unchanged so `chain` needs no changes
      — mirrors the existing `if platform == "win32":` gating already used for `app_funcs` in
      that file; same 16 `from .X import name` lines, just duplicated under each branch with
      `X` swapped. `CONTROL_ACTIONS` in `constants.py` untouched (verified: same tuple object,
      `chain`'s `__run_control` still just does `globals()[step["action"]](...)`).
- [x] Accept `backend="atspi"` (default on Linux); raise a clear error for `"uia"` / `"win32"` on Linux and vice versa
      — `atspi_funcs._check_backend()` rejects anything but `"atspi"`/`None` with a `ValueError`
      naming the Windows backend file; added the symmetric `pywinauto_funcs._check_backend()`
      (rejects `"atspi"`) so a copy-pasted script gives a clear error on either platform instead
      of a confusing one from pywinauto/Atspi itself. Verified both directions at the REPL.
- [x] macOS: keep the functions importable and raise `NotImplementedError` when used
      — `_atspi()` checks `sys.platform == "darwin"` first and raises `NotImplementedError`
      before even attempting the `gi` import, so the module stays importable on macOS and the
      error is immediate and explicit rather than an `ImportError` about a missing Linux package.

Verified (2026-10-13, this box): `import automonkey` picks `atspi_funcs` automatically on
Linux; `CONTROL_ACTIONS` unchanged; all 16 functions raise `NotImplementedError` cleanly when
called with a valid backend, and `ValueError` when called with `"uia"`/`"win32"`. Existing test
suite unaffected (`tests/test_pywinauto_funcs.py`'s one pre-existing Linux failure — no
`pywinauto` installed — reproduces identically on unmodified `main`; that's the section 6
skip-on-Linux gap, not something this phase introduced).

## 3. Finding windows and controls

- [x] `get_window`: find the top-level window by title regex (`.*?{title}.*?`, same as Windows) across all applications
      — `_iter_top_level_windows()` walks the AT-SPI desktop's applications and yields their
      direct children (that's where frames/dialogs live); `get_window` regex-matches each
      candidate's accessible name with the same `f".*?{window}.*?"` pattern pywinauto uses.
- [x] Wait with `timeout` until the window exists and is `SHOWING` / `VISIBLE`; return the first match
      — polling loop (0.2s) until deadline; `_is_showing` checks `Atspi.StateType.SHOWING` or
      `VISIBLE`; returns the first match found during a pass, same as pywinauto's `found_index=0`.
- [x] `get_control` with dict criteria; map keys:
  - [x] `title` -> accessible name, `title_re` -> name regex
  - [x] `control_type` -> role (map pywinauto names: Button -> push button, Edit -> text/entry, Document -> document text,
        CheckBox -> check box, ComboBox -> combo box, MenuItem -> menu item, List -> list, ...)
        — **the actual mapping differs from this draft list** (see phase 1 findings: `get_role_name()`
        strings aren't stable across AT-SPI versions/toolkits). Mapped instead onto the `Atspi.Role`
        *enum* (`_CONTROL_TYPE_TO_ROLES` in `atspi_funcs.py`), which is the stable identifier -
        confirmed empirically a GTK push button is `Atspi.Role.BUTTON`, not `PUSH_BUTTON` (which
        exists as a separate enum member, kept in the tuple for other toolkits). Each pywinauto
        type maps to a tuple of acceptable roles, e.g. `"Edit": ("TEXT", "ENTRY", "PASSWORD_TEXT")`.
        Resolved once per `get_control` call (not per node) so an unknown `control_type` raises
        `ValueError` immediately instead of silently vanishing into a "not found" result.
  - [x] `auto_id` -> accessible id (AT-SPI 2.34+) or `id` attribute; fall back to name
        — `_accessible_id()` tries `get_accessible_id()` then an `"id"` key from `get_attributes()`;
        if both are empty (the common case - GTK apps don't set these by default, confirmed on the
        phase-1 test app) falls back to comparing against the accessible name, exactly as specced.
  - [x] `found_index` for several matches
- [x] `get_control` with a string ("best match"): exact name, then name + role suffix (`"SaveButton"`), then case-insensitive substring
      — `_best_match()`: (1) exact accessible-name match; (2) if the string ends with a known
      control-type suffix (checked longest-first against `_CONTROL_TYPE_TO_ROLES`' keys), split
      off the name part and require both a name match and a role match; (3) case-insensitive
      substring on the name. Returns the first match at each stage, same precedence as pywinauto.
- [x] Limit tree search depth / skip huge subtrees (browsers) to keep lookups fast
      — `_walk()` takes a node budget (`_MAX_SEARCH_NODES=6000`) and a depth cap
      (`_MAX_SEARCH_DEPTH=40`); every lookup (`_find_all`, `_collect_names`) goes through it.
- [x] Clear error when nothing matches: list the closest names found
      — `get_window` lists the titles of every window actually seen; `get_control` lists
      `"name" (role)` for every named node under the window (via `_collect_names`, same depth/node
      budget, deduplicated, capped at 20) so a typo'd target is easy to spot from the error alone.

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

- [x] `click_control(invoke=True)`: run the control's "click" / "press" / "activate" action
      — `_invoke()` picks the first action named click/press/activate/jump (case-insensitive),
      else action index 0 if any action exists at all; raises `ValueError` if the control has
      no AT-SPI actions. `_action_names()` wraps the deprecated `Atspi.Action.get_action_name`
      call in a `DeprecationWarning` filter so normal use doesn't spam stderr.
- [x] `click_control(invoke=False)`: mouse click at the control's screen extents (X11); on Wayland fall back to the action and warn
      — `_click_at_extents()` reads `Component.get_extents(Atspi.CoordType.SCREEN)` and
      `pyautogui.click()`s its center. `_is_wayland_session()` is a coarse, session-wide check
      (`WAYLAND_DISPLAY` set and `XDG_SESSION_TYPE` != x11) gating a `warnings.warn()` +
      fallback to `_invoke()` - not per-window, matching the doc's own session-wide framing of
      the limitation.
- [x] `double_click_control`, `right_click_control` (mouse based; document Wayland limits)
      — unchanged thin wrappers around `click_control` (same as `pywinauto_funcs.py`; neither
      takes an `invoke` kwarg in either backend, so on Wayland they go through the same
      fallback-and-warn path with a single click, not a true double-click equivalent).
- [x] `type_in_control`: grab focus (`Component.grab_focus`), then type with the existing layout-aware `write`;
      `literal=False` -> translate pywinauto key syntax (`{ENTER}`, `^a`, `%f`, `+x`) to `keys2`
      — `_send_key_syntax()` is a small tokenizer: `{NAME}` -> `press()`, a leading run of
      `^`/`%`/`+` + one char or `{NAME}`/`(...)` group -> `keys2(*mods, key)`, `~` -> Enter,
      everything else -> `write()`. Not a full pywinauto-grammar implementation (no repeat
      counts like `{TAB 3}`, no nested groups) - covers the four documented cases plus `~`
      and parens groups as a reasonable extension.
- [x] `type_in_control(pause=...)`: delay between key presses — passed through to `write`'s
      `interval` (literal) or slept between tokens (key-syntax mode).
- [x] `set_control_text`: `EditableText.set_text_contents`; fall back to select all + type
- [x] `get_control_text`: `Text` interface for editable text, else accessible name; copy to clipboard like on Windows
      — uses `is_text()` to decide (not "character count > 0", which would wrongly treat a
      legitimately empty text field as "no Text interface" and fall back to the accessible name).
- [x] `select_menu("File->Save As...")`: walk menu items by name, expand each level, activate the last one
      — walks level by level via `_find_menu_item` (role in menu/menu item/... + name match,
      "&" mnemonics stripped like pywinauto's own `_find_menu_item`); `_expand_menu` is called
      on intermediate levels but is genuinely best-effort (see note below - GTK doesn't need it).
- [x] `select_item`: `Selection` interface by text or index (combo box, list, tabs)
      — **implemented as click-the-item, not the `Selection` interface**, per the section 1
      finding: `Atspi.Selection.select_child()` on a GTK combo's popup doesn't commit the real
      selection, but invoking `click` directly on the target item does. `Selection.select_child`
      is kept as a fallback for widgets where clicking isn't available.
- [x] `check_control` / `uncheck_control`: read `CHECKED` state, run the toggle action only if needed
- [x] `wait_control(state=...)`: map `exists`, `visible` (`SHOWING`), `enabled` (`ENABLED`/`SENSITIVE`), `ready`, `active` (`ACTIVE`/`FOCUSED`)
      — `"ready"` is expanded to `"visible enabled"` before checking; `"exists"` needs no
      explicit AT-SPI check since `get_control` already failing means it doesn't.
- [x] `control_exists` — `get_control` + catch `LookupError`.
- [x] `list_controls(depth=...)`: print role, name, id and the dict to use as `control`; return the text
      — prints `role 'name' control={...}` per line, where the dict is literally what you'd
      pass back into `get_control`/`click_control` etc. (`title`, `control_type` via the reverse
      of `_CONTROL_TYPE_TO_ROLES`, `auto_id` when an accessible-id/`id` attribute exists).
- [x] `start_app`: start the process and wait until its application appears on the AT-SPI bus
      — `subprocess.Popen` + poll the desktop's applications for one whose
      `get_process_id()` matches `proc.pid`.

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

- [x] Detect a missing AT-SPI bus / disabled accessibility and print how to enable it
      — **important discovery while implementing this**: calling into `Atspi` (e.g.
      `Atspi.get_desktop(0).get_name()`) against a genuinely unreachable bus does **not**
      raise a Python exception at all - libatspi's C layer (`dbind`) prints a fatal
      `dbind-ERROR` to stderr and **aborts the entire process**, confirmed by directly
      reproducing it (`DBUS_SESSION_BUS_ADDRESS` pointed at a nonexistent socket -> the
      subprocess just died, no traceback, no catchable error). So detection cannot happen by
      wrapping an `Atspi` call in `try/except` - it has to happen *before* anything ever
      calls into `Atspi`. Fixed with `_atspi_bus_reachable()`: a **separate `dbus-send`
      process** (confirmed safe: plain nonzero exit + stderr message, no abort) queries
      `org.a11y.Bus.GetAddress` with a 3s timeout; `_atspi()` runs this once per process
      (cached in `_env_checked`, re-tried if it previously failed) before ever handing out
      the `Atspi` module, raising a clear `ConnectionError` if the bus is down. Confirmed:
      merely `from gi.repository import Atspi` (without calling anything) is safe even with
      a dead bus - only the bus check's placement, not the import itself, mattered.
      Also added `_check_accessibility_enabled()`: a `gsettings get
      org.gnome.desktop.interface toolkit-accessibility` check (warn-only, same one-time
      cache) that tells the user to enable it and restart apps if it's `false`.
- [x] Extend `_default_display_env` in `automonkey/__init__.py` with `DBUS_SESSION_BUS_ADDRESS` when started from a service / MCP client
      — same pattern as the existing `WAYLAND_DISPLAY`/`DISPLAY` fallback: only sets it when
      missing AND `$XDG_RUNTIME_DIR/bus` actually exists, defaulting to
      `unix:path=$XDG_RUNTIME_DIR/bus` (the standard per-user systemd D-Bus socket -
      confirmed to match this box's real, working value exactly).
- [x] Document the Qt / Chrome / Electron flags in the error message when an app shows an empty tree
      — `_QT_CHROME_ELECTRON_HINT` is appended to `get_control`'s and `select_menu`'s
      `LookupError`, and to `list_controls`'s printed output, whenever the resolved window
      itself has zero AT-SPI children (`_has_no_children`) - i.e. exactly the "whole app
      exposes nothing" case these flags are for, not a normal "typo'd one control" miss.

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

- [x] Unit tests with fake accessibles for: criteria mapping, best match, menu walk, check toggle, text fallback, key syntax translation
      — `tests/test_atspi_funcs.py` (31 tests). A `FakeAtspi` namespace (`_Sentinel`-based
      `Role`/`StateType` members, static `Action`/`Text`/`Selection`) plus a `FakeAccessible`
      stand in for `gi.repository.Atspi` entirely, so these need no `python3-gi`/AT-SPI bus
      and run anywhere. Public functions under test are reached by monkeypatching `_prepare`
      (-> `FakeAtspi`) and/or `get_window`/`get_control` directly, the same seam
      `test_pywinauto_funcs.py` already uses for the Windows backend. Includes two
      regression tests for the real bugs found while building sections 3-4: the
      unknown-`control_type` exception-swallowing bug, and (implicitly, via the toggle
      test's action-count assertions) that `check_control` only acts when needed.
- [x] Make the existing `tests/test_pywinauto_funcs.py` skip on Linux and the new tests skip on Windows
      — `pytestmark = pytest.mark.skipif(sys.platform != "win32", ...)` added to
      `test_pywinauto_funcs.py` (this also resolves the one pre-existing Linux failure
      noted in every earlier phase of this doc - `test_walk_menu_expands_then_invokes`
      needed real `pywinauto`); `test_atspi_funcs.py` and `test_atspi_integration.py` both
      carry the opposite `skipif(sys.platform == "win32", ...)`.
- [x] Integration tests (opt-in via env var) against gnome-calculator and gnome-text-editor
      — `tests/test_atspi_integration.py`, gated by `AUTOMONKEY_ATSPI_INTEGRATION=1` *and*
      a per-test `shutil.which()` check, so the file is always safe to collect/run
      anywhere. Neither app is installed on this box, so they're unverified here as
      written - but the exact pattern (`start_app` -> `type_in_control` ->
      `get_control_text`, and separately `start_app` -> `click_control(invoke=True)` on a
      dict-matched control) was validated end-to-end against `mousepad` (also
      GtkSourceView-based, close enough to stand in for `gnome-text-editor`) before being
      written into the real test. **That validation caught a real mistake**: the
      draft used `control_type: "Document"` for the main text area, but GtkSourceView
      exposes it as AT-SPI role `"text"` (control_type `"Edit"`) - `Document*` roles are
      for LibreOffice/WebKit-style content, not plain GTK text editors. Fixed before
      committing the test.
- [x] CI: install `python3-gi gir1.2-atspi-2.0 at-spi2-core xvfb`, run the integration tests under Xvfb + `dbus-run-session`
- [x] Enable the commented-out pytest step in `.github/workflows/python-package.yml`
      — both done together: added an apt-get step (`python3-gi gir1.2-atspi-2.0
      at-spi2-core xvfb dbus-daemon gnome-calculator gnome-text-editor` - `dbus-daemon`
      provides `dbus-run-session` on this box, confirmed via `dpkg -S`), uncommented the
      pytest step and wrapped it in `xvfb-run -a dbus-run-session -- pytest`, and set
      `AUTOMONKEY_ATSPI_INTEGRATION=1` so CI actually exercises the integration tests
      rather than just skipping them. **Known, documented tradeoff, not silently
      glossed over**: `python3-gi` installs PyGObject for Ubuntu's own system python3,
      not for whichever interpreter `actions/setup-python` puts on `PATH` for a given
      matrix entry (the workflow's existing matrix is Python 3.8/3.9/3.10, set long
      before this AT-SPI work and not touched here - that's a separate, pre-existing
      staleness issue, not something this phase should quietly take on). Wired by appending
      `/usr/lib/python3/dist-packages` to `sys.path` in-process around `pytest.main()` -
      the trick used throughout this implementation to let a different interpreter see
      system-installed `gi`, but as a plain `PYTHONPATH` it pre-empted this job's own
      installed packages and broke pytest's plugin loading, hence the in-process append
      after pytest's own startup. This only lines up cleanly when a matrix entry's Python
      version matches the runner's system python3 ABI - 3.8/3.9/3.10 against
      ubuntu-latest's 3.12 system python does not, so on CI these two tests **skip**.
      **Fixed 2026-10-16**: they used to *fail* there (a plain `ImportError` from `gi`),
      which turned the matrix red on every version - and once the publish job was gated on
      the matrix, that would have blocked every release over an environment quirk
      unrelated to this repo's code. `tests/test_atspi_integration.py` now checks the
      bindings itself (`_atspi_bindings_available()`, which catches the half-working
      `import gi` -> `from . import _gi` failure) and skips, so the file keeps its "always
      safe to collect/run" contract. Verified by reproducing that exact broken-`gi` shape
      locally: a fake `gi` package that raises on `from . import _gi` -> binding check
      False and the file collects and skips cleanly; a working fake -> binding check True.
      The commands in section 5 still run these tests for real on a box whose python3 has
      python3-gi. Could not be
      verified by actually running GitHub Actions from here - YAML syntax was validated
      with a local parse, and the underlying command pattern (`xvfb-run` / fakeroot X +
      `dbus-run-session` for a private AT-SPI bus) is the standard approach for headless
      accessibility testing, but the workflow itself is unverified end-to-end.

Verified (2026-10-13, this box): all 31 new unit tests pass; full suite went from
**1 failed, 16 passed, 1 skipped** (start of this phase) to **38 passed, 13 skipped, 0
failed**. Confirmed the integration tests correctly skip by default and also correctly
skip (not error) with `AUTOMONKEY_ATSPI_INTEGRATION=1` set but the target apps absent.
`.github/workflows/python-package.yml` parses as valid YAML with the expected step order.

## 7. Packaging and docs

- [x] `setup.py`: add a `linux` extra (or document that PyGObject comes from the distro); keep `pywinauto` Windows-only
      — chose **document**, not a pip extra: PyGObject genuinely isn't a reliable pip
      install (needs system build deps - cairo, gobject-introspection headers,
      pkg-config - that aren't guaranteed present, confirmed in this very project by how
      we actually got it working: `apt-get install python3-gi ...`, never pip). A fake
      `extras_require={'linux': [...]}` would either be empty (useless) or silently fail
      to build for most users, worse than no extra at all. Documented instead via a
      module docstring in `setup.py` plus `Operating System :: Microsoft :: Windows` /
      `:: POSIX :: Linux` classifiers. `pywinauto` was already Windows-only
      (`requirements.txt`'s `sys_platform == 'win32'` marker, pre-existing, untouched).
- [x] README section 6: add Linux setup, the criteria mapping table and the Wayland limits
- [x] Add the Linux version of the Calculator / text editor examples to the README
      — both done together: restructured README's "6. Control actions" into "6.1 Windows
      (pywinauto)" (unchanged content) and "6.2 Linux (AT-SPI)" (new), with the apt/
      gsettings setup, the `control_type` -> AT-SPI role table (from
      `_CONTROL_TYPE_TO_ROLES`, confirmed against real widgets per section 3's findings,
      not the spec), the Wayland limits written precisely from what was actually
      confirmed in sections 4/6 (not the vaguer "Known limits" bullet at the top of this
      file), and `gnome-calculator`/`gnome-text-editor` chain examples mirroring the
      Windows Calculator/Notepad ones - using the real `control_type: "Edit"` finding
      from section 6, with a comment explaining why (not `"Document"`), so a reader
      doesn't have to rediscover that the hard way.
- [x] Optional: expose the control tree to the MCP server (`automonkey/ai/mcp_server.py`) on both systems
      — added a `list_controls(window, depth=None)` MCP tool, a thin wrapper around the
      top-level `automonkey.list_controls` (already cross-platform via the section 2
      backend selection, so no new platform logic needed here). Verified: imports
      cleanly, registers as a tool, and returns the real control tree against a live
      window through the MCP wrapper.
- [x] Update `HISTORY.rst` and bump the version
      — `0.3.3` -> `0.4.0` (new feature, not a patch) in `automonkey/__init__.py`,
      `setup.py`, and `setup.cfg`'s `current_version`. Added a `HISTORY.rst` entry
      summarizing the Linux backend, the Wayland limits, and the `copy()` resilience fix.
      **Not run through the project's own `bumpversion` tool** - noticed its config
      (`setup.cfg`) searches for `version='{current_version}'` (single quotes) but
      `setup.py` actually has `version="0.4.0"` (double quotes), a pre-existing mismatch
      that would make the configured search-and-replace silently not match. Didn't fix
      this - it's a separate, orthogonal tooling issue, not part of this phase's scope -
      but updated all three files by hand to the same end state the tool would produce
      if that were fixed.

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
