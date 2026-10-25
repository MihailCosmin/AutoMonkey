---
name: visual-testing
description: Thorough visual and user-experience testing of desktop apps (Qt/PySide6, egui, Flutter, tkinter, DearPyGui, WinUI, Win32, Electron) the way a real user would - clicking every menu, button and link, typing, dragging, scrolling, key combos, dialogs, tab order, clipped text and layout - with the AutoMonkey MCP (mcp__automonkey__*) driving the real mouse and keyboard, plus headless framework tests (egui_kittest, pytest-qt, Flutter goldens/integration_test) for CI. Use whenever the user asks to test, verify, QA, check, evaluate or review a UI, a window, a dialog, a workflow or the UX of an app, to confirm a UI change works in the real app, or to hunt UI bugs; also when finishing UI work that needs to be seen working.
---

# Visual testing of desktop apps

Two layers. **Layer 2 is the most critical one and is never skipped.**

| | Layer 2 - AutoMonkey user pass (**MOST CRITICAL**) | Layer 1 - framework tests (support) |
|---|---|---|
| What | The real app, real window, real mouse and keyboard, judged with your eyes | Headless tests inside the framework |
| Finds | Everything a user meets: dead menu items, broken drags, wrong tab order, clipped or overlapping text, dialogs that don't close, focus lost, layout at other sizes, real input bugs | Logic regressions, cheaply, on every commit |
| Tools | `mcp__automonkey__*` (or `python -m automonkey.ai` in a shell) | egui_kittest, pytest-qt, Flutter goldens + integration_test |
| Runs | On this desktop, while the user waits | In CI, no screen |

Layer 1 passing proves nothing about what the user sees. A UI task is done only after
the layer-2 pass has exercised **every** control the change touches - and for a full
test, every control in the app.

## 0. Before you start

1. Check that the `mcp__automonkey__*` tools exist (load them with ToolSearch
   `+automonkey`). Without them use the CLI with the AutoMonkey venv's Python
   (`<AutoMonkey>\.venv\Scripts\python -m automonkey.ai do "<script>"`, `bin/python` on
   Linux); it prints a screenshot path - open it with Read. Install/register both with
   `python -m automonkey.ai install-claude` from the AutoMonkey repo.
2. **Tell the user you are about to take over the mouse and keyboard** and that pushing
   the mouse into a screen corner stops you (fail-safe). Never fight the user for the
   mouse: if a step reports the fail-safe, stop and ask.
3. Build/start the app from the repo you are testing. Use **test data**: a copy of a
   sample file, a temp folder, a fresh profile - never the user's real documents.

## 1. Safety rules (non-negotiable)

- **Never type into, save over or close a window you did not open.** `launch` stops with
  "reused the window ..." when an app was already running and its existing window came
  back (Windows 11 Notepad does this with all the user's tabs). Then open a fresh document
  first (`hotkey ctrl+n`) and check the screenshot, or ask the user to close the app.
- Text checks read only the **active window**, so make sure the app under test is in
  front (`focus`). `screen:` searches everything - including your own terminal showing
  the test script, which gives false passes.
- `kill` only processes you launched. Close the app under test in a `finally:` block.
- Don't send screenshots of the whole desktop to other services (the swarm, web): they
  show the user's other windows. Crop to the app (`zoom`, or `save` + crop) first.
- Destructive actions inside the app (delete, overwrite, send, publish) only on test data.

## 2. Layer 2: the user pass - test it like a person, completely

### 2.1 Start and look

```
act("launch <command>; maximize <title>")      # returns a log + screenshot
controls("<title>")                            # every interactive control + click point
```

Read the screenshot as a user would before touching anything: does the first screen
make sense, is anything cut off, misaligned, unreadable, empty that shouldn't be?

### 2.2 Make the coverage list

Write `ui-test/coverage.md` in the repo under test (or the scratchpad if the user doesn't
want files there): one line per thing a user can do, built from

- `controls(window)` - buttons, fields, checkboxes, combos, lists, tabs, links, sliders;
- every menu: open it (`click_control File`), then `controls` again - open menus and
  context menus are listed with their items **and shortcuts** (`Save\tCtrl+S`);
- right-click menus on each kind of area (`rclick X Y`, then `controls`);
- toolbars, status bar, splitters (`Thumb`), resize grip, tray icons;
- every dialog reachable from the above (repeat the inventory inside each);
- keyboard: every shortcut shown in menus, Tab/Shift+Tab, Enter/Escape, Alt mnemonics,
  arrows in lists/trees, Ctrl/Shift multi-select, Delete, undo/redo, copy/paste;
- mouse gestures: double-click, drag-and-drop (reorder, move between panes, files in),
  drawing/selection on canvases, scroll and Ctrl+scroll zoom, hover tooltips;
- window: resize small and large, maximize/restore, minimum size, second monitor if any.

Mark each line `[ ]`; tick it `[x] ok` or `[x] BUG-n` as you go. **Nothing is "tested"
until it was actually exercised in the running app.**

### 2.3 Exercise everything

Batch the steps you are sure of into one `act`; look at the screenshot and the change
summary after each batch. Prefer names over pixels: `click_control Save`,
`drag_control Alpha to Delta`; use coordinates from the **latest** screenshot only when
a control has no accessible name (canvases, custom-drawn widgets).

For each control, do what a user would, then check the effect with `expect_*`:

| Control | Do at least |
|---|---|
| menu item / button / link | click; the promised thing happens (`expect_window`, `expect_text`, `expect_change`) - **a click that changes nothing is a bug** |
| text field | type normal text, empty, very long, non-ASCII (`Zoë ăîșț 中文`), invalid input; Enter; paste |
| checkbox / radio / toggle | toggle on and off; dependent controls enable/disable |
| combo / list / tree | open, pick by mouse and by keyboard, scroll, multi-select, reorder by drag |
| canvas / editor | `stroke` / `drag`; undo (`hotkey ctrl+z`) and redo; zoom |
| dialog | open; OK, Cancel, Escape, the X button; Enter submits; `tab_order 8` follows the visual order; validation messages |
| splitter / resize | `drag` the `Thumb`; resize the window; nothing overlaps or disappears |
| shortcut | every one from the menus, also with the focus in a text field |
| destructive / unsaved | close with unsaved changes -> the prompt appears; Cancel keeps the work |

Assertions to use: `expect_text`, `expect_no_text`, `expect_window`, `expect_no_window`,
`expect_focus`, `expect_control`, `expect_order A, B, C`, `expect_change`,
`expect_no_clipped`. They retry for 3 s, so they don't race the app's repaint.

### 2.4 Judge what you see (every screen, every dialog, every state)

Run `clipped` on every window and dialog - it compares each label's real text (from the
accessibility tree) with what OCR reads in its box and reports cut-off text. Then look:

- text: clipped, elided, overlapping, wrapped badly, typos, mixed languages, placeholder
  text left in;
- layout: misaligned columns, inconsistent spacing/margins, controls outside the window,
  scrollbars where none are needed, empty areas, bad behaviour when resized;
- state: focus visible, disabled controls look disabled, selection visible, busy/loading
  feedback, empty states, error messages that say what to do;
- consistency: same action named the same everywhere, same shortcut conventions,
  OK/Cancel order, title bars and dialog titles;
- contrast and readability in the app's theme(s); `zoom` to read small text precisely.

### 2.5 Record every bug so it can be replayed

For each bug:

1. Reduce it to the shortest steps. `history` returns the scripts you ran, ready to copy.
2. Save `tests/ui/bugs/<short-name>.amk` in the app's repo: a comment saying what is
   wrong and what is expected, the steps, an `expect_*` for the **correct** behaviour (so
   the script fails while the bug exists and passes once it is fixed), then
   `finally:` + cleanup. Example:

   ```
   # BUG: in Edit > Preferences, Tab goes from User to OK instead of Email.
   # Expected: User, Email, Dark mode, OK, Cancel.
   launch .venv\Scripts\pythonw.exe app.py
   click_control Edit
   click_control Preferences...
   click_control prefUser
   key tab
   expect_focus Email
   finally:
   kill My App
   ```
3. `replay` it once to confirm it fails; the failure screenshot is saved next to it as
   `<name>.failure.png` (evidence).
4. Flows that work go into `tests/ui/<flow>.amk` as regression scripts.

`replay` (MCP) or `python -m automonkey.ai replay tests/ui/*.amk tests/ui/bugs/*.amk`
(exit code 1 on any failure) re-runs them all; run it after every fix.

### 2.6 Report

End with: the coverage list (what was exercised, what was not and why), the bugs ranked
by severity with their `.amk` script and screenshot, and the visual findings. Never
report "tested" for something you only read in the code.

## 3. Layer 1: framework tests for CI

Add or extend headless tests for what the user pass covered, so regressions are caught
without a screen. Read the reference for the app's framework:

- egui / eframe: [references/egui.md](references/egui.md) (`egui_kittest` 0.37, snapshots)
- Qt / PySide6 / PyQt, tkinter, DearPyGui: [references/qt.md](references/qt.md) (pytest-qt, goldens)
- Flutter desktop: [references/flutter.md](references/flutter.md) (widget tests, goldens, integration_test)

A bug found in layer 2 gets both: its `.amk` script and, where the framework can express
it, a layer-1 test.

## 4. AutoMonkey quick reference

Full reference: [references/automonkey.md](references/automonkey.md). Essentials:

- `act(script, screenshot=True)` runs many steps (`;` or newline separated) and returns
  the log, what changed on screen, and a screenshot. `screenshot=false` saves tokens.
- Coordinates are always pixels of the **latest screenshot** you were shown.
- `controls(window)` = click points of every control, `DISABLED` and toggle states;
  `windows()` = open windows; `zoom(x,y,w,h)` = enlarged view; `find_text` / `read_text`
  = OCR.
- Mouse input is real (SendInput): hover, drags and strokes reach every app, including
  WinUI and canvas widgets. `keydown ctrl; click ..; keyup ctrl` for modifier clicks.
- `tab_order N` reports the focused control after each Tab; `focused` the current one.
- A failed step stops the script and says which step and why; `finally:` steps still run.

## 5. When things don't work

- "could not bring ... to the foreground": the app may run elevated (as administrator)
  - Windows then blocks input from a normal process. Run the app non-elevated.
- `controls` shows nothing useful: the UI draws itself without an accessibility tree
  (DearPyGui, games, some custom canvases). Use screenshots, `zoom`, `find_text`,
  `click_text` and coordinates; say in the report that the app has no accessibility
  tree (that is itself an accessibility bug).
- OCR misses tiny or low-contrast text: `expect_text` then falls back to the
  accessibility tree automatically; otherwise `zoom` and read it yourself.
- Several monitors: `act("monitor 1")` switches the screenshots and clicks to monitor 1.
- Linux: the same tools work on X11/XWayland through AT-SPI; start apps with `launch`.

## 6. Using the swarm (cheap-ai-swarm)

Good swarm tasks around this skill: writing layer-1 tests from the coverage list (with
the framework's test command as `check`), turning bug notes into `.amk` scripts, and
second-opinion visual reviews of **cropped** app screenshots (`images`, `vision`-tagged
providers). Keep the user pass itself, the judgment and the final report for yourself.
