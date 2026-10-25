# AutoMonkey reference (generated from the code)

AutoMonkey drives the real mouse and keyboard. All coordinates are pixels of the latest
screenshot you were shown; the server maps them to the screen (any DPI, any monitor).

## MCP tools

### `act(script: str, screenshot: bool = True, grid: int = 0)`

Run an action script (one command per line or ';'-separated), wait for the screen to
settle, then return the step log, what changed, and a screenshot.

Commands: click X Y [button] [N] | dclick X Y | rclick X Y | mclick X Y | move X Y |
drag X1 Y1 X2 Y2 [button] | path/stroke X1 Y1 X2 Y2 .. | press/release [BUTTON] |
scroll N [X Y] | hscroll N [X Y] | type TEXT | key K [K..] | hotkey ctrl+l | keydown K | keyup K |
wait S | stable [T] | change [T] | url ADDRESS | launch CMD | focus WINDOW | maximize [WINDOW] |
close WINDOW | kill WINDOW (only apps you launched) | monitor N | click_text TEXT |
wait_text TEXT | click_image PATH | click_control NAME [in WINDOW] |
drag_control NAME to NAME [in WINDOW] | focused | tab_order N [shift] | clipped [WINDOW] |
expect_text TEXT | expect_no_text TEXT | expect_window TITLE | expect_no_window TITLE |
expect_focus NAME | expect_control NAME [in WINDOW] | expect_order A, B, C [in WINDOW] |
expect_change [T] | expect_no_clipped [WINDOW] | save PATH
Text steps look in the active window only ("screen: TEXT" searches everywhere).
expect_* steps retry for 3 s and stop the script when they fail; steps after a line
`finally:` always run (close the app under test there).

Example: "launch notepad; type Hello; expect_text Hello; hotkey ctrl+a; key delete"
Set screenshot=false when you don't need to look (saves tokens); grid=100 adds a grid.

### `screenshot(grid: int = 0)`

Take a screenshot. grid=N overlays labelled lines every N pixels for precise coordinates.

### `zoom(x: int, y: int, width: int, height: int, grid: int = 0)`

Enlarged full-resolution view of a screenshot region (screenshot coordinates), for small
text or precise targeting. Grid labels, if requested, use the same screenshot coordinates.

### `windows()`

List open windows ('*' = active) with ids, titles and their screenshot-coordinate bounds.

### `controls(window: str, interactive_only: bool = True, depth: int = None, max_items: int = 400)`

Every control of a window from the accessibility tree, with the click point of each
in screenshot coordinates, DISABLED / toggle states, and automation ids (Windows).

Use it to test COMPLETELY: list the interactive controls (menus, buttons, links, fields,
tabs, list items), then exercise each one with `act` (click_control NAME, or click X Y).
Menus only show their items while open: open the menu, then call this again.
window: title substring, process name (e.g. "notepad.exe") or window id.

### `list_controls(window: str, depth: int = None)`

List a window's controls via the OS accessibility tree (pywinauto on Windows,
AT-SPI on Linux; not implemented on macOS yet) - role, name and the dict to pass as
`control` to click/type/etc. Use this instead of screenshots/OCR when the app exposes
an accessibility tree (most GTK/Qt/native apps do; Electron needs
--force-renderer-accessibility, canvas-drawn UIs don't expose one at all).

window: title of the top-level window, regex matched anywhere in the title.
depth: how many levels deep to go (default: all).
On Windows prefer `controls`, which is shorter and gives click points.

### `find_text(text: str)`

Locate text on screen via OCR. Returns boxes and click points in screenshot coordinates.

### `read_text(x: int = 0, y: int = 0, width: int = 0, height: int = 0)`

OCR the screen (or a region in screenshot coordinates) and return the text. Cheaper than
a screenshot when you only need to read.

### `replay(path: str)`

Run a saved .amk regression script (action-script steps, '#' comments, expect_* checks).
Returns PASSED/FAILED with the step log; on failure also a screenshot, and the
full-resolution screen is saved next to the script as <name>.failure.png.

### `history(n: int = 20)`

The last n action scripts run today (with ok/FAILED), as .amk text. Copy the steps
that reproduce a bug into a regression file (add expect_* checks), then `replay` it.

## Action script language (`act`, `.amk` files, `python -m automonkey.ai do`)

```
A tiny action language so an AI can do many steps in ONE tool call.

One command per line (or separated by ';'; write '\;' for a literal ';'). Lines that
start with '#' are comments. Coordinates are image pixels of the latest screenshot.

Mouse (real input events: hover, drags and strokes reach every app):
    click X Y [left|right|middle] [N]   dclick X Y    rclick X Y    mclick X Y
    move X Y      (glides there: hover effects and tooltips fire)
    drag X1 Y1 X2 Y2 [button]           (press, glide, release - drag-and-drop, sliders, splitters)
    path X1 Y1 X2 Y2 ...                (press, glide through every point, release: freehand)
    stroke X1 Y1 X2 Y2 ...              (same as path)
    press [BUTTON]    release [BUTTON]  (hold a button across other steps)
    scroll N [X Y]    hscroll N [X Y]   (N>0 up / right, N<0 down / left)
Keyboard:
    type TEXT...      key K [K...]      hotkey ctrl+shift+t
    keydown K         keyup K           (hold a key, e.g. keydown ctrl; click ...; keyup ctrl)
Waiting:
    wait SECONDS      stable [TIMEOUT]  change [TIMEOUT]
Windows and apps:
    launch COMMAND... focus WINDOW      maximize [WINDOW]   close WINDOW   monitor N
    kill WINDOW       (end the window's process - ONLY for an app the test itself launched)
Lines after a line `finally:` always run, even after a failure: close the app under test there.
    url ADDRESS                         (focus address bar, type, Enter, wait for load)
Finding things:
    click_text TEXT...                  wait_text TEXT...   (OCR, needs tesseract)
    click_image PATH                    (template match)
    click_control NAME [in WINDOW]      (accessibility tree; real mouse click on its centre)
    drag_control NAME to NAME [in WINDOW]  (drag-and-drop between two controls' centres)
    focused                             (which control has the keyboard focus)
    tab_order N [shift]                 (press Tab N times, report the focused control each time)
    clipped [WINDOW]                    (labels whose text is cut off: accessibility name vs OCR)
Text steps (click_text, wait_text, expect_text, expect_no_text) read only the ACTIVE
window, so text elsewhere (a terminal showing this very script) can't match; prefix the
text with "screen:" to search the whole screen, e.g. `expect_text screen: Saved`.
Checks (a failed check stops the script - use them in saved regression scripts):
    expect_text TEXT...       expect_no_text TEXT...      expect_window TITLE
    expect_no_window TITLE    expect_focus NAME           expect_control NAME [in WINDOW]
    expect_change [TIMEOUT]   (the screen changed since before the previous input step)
    expect_no_clipped [WINDOW]
    expect_order NAME, NAME, ... [in WINDOW]   (controls appear top-to-bottom in this order)
Evidence:
    save PATH                 (save a full-resolution screenshot, e.g. for a bug report)
```

## Command line (shell-only agents, CI)

```
Command line for agents that only have a shell (one command = act + screenshot).

    python -m automonkey.ai shot [--grid 100]
    python -m automonkey.ai do "launch firefox; maximize; url google.ro"
    python -m automonkey.ai zoom X Y W H
    python -m automonkey.ai windows
    python -m automonkey.ai find "Accept all"
    python -m automonkey.ai read [X Y W H]
    python -m automonkey.ai controls "Notepad" [--all] [--depth N]
    python -m automonkey.ai history [N]
    python -m automonkey.ai replay tests/ui/*.amk      (exit code 1 if any script fails)

Screenshots are written to --out (default: $AUTOMONKEY_AI_OUT or
/tmp/automonkey_ai/screen.png) and the path is printed; open it to look.
Coordinates are pixels of that screenshot.
```

## Files and environment

- Session log: every `act` script is appended to
  `~/.cache/automonkey/sessions/<date>.jsonl` (`AUTOMONKEY_SESSION_DIR`); `history` reads it.
- `AUTOMONKEY_EXPECT_TIMEOUT` (default 3 s): how long `expect_*` steps retry.
- `AUTOMONKEY_MONITOR`: monitor index to start on. `AUTOMONKEY_AI_MAX_SIDE` (default 1280):
  longest side of the screenshots you get.
- `TESSERACT_CMD`: path of tesseract when it is not found automatically (OCR).
