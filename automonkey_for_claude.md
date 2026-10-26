# AutoMonkey for Claude

Instructions for any Claude model controlling this computer graphically with AutoMonkey's
AI layer (`automonkey/ai/`). For **testing an app's UI**, follow the `visual-testing` skill
(`skills/visual-testing/SKILL.md`); this file is the tool manual it builds on.

## Why the AI layer exists

Raw pyautogui costs about 3 tool calls per step (act, screenshot, look at the image), and
you have to guess how long to wait and convert coordinates by hand. The AI layer folds
all of that into one call: run many steps, wait until the screen settles, report what
changed, return a screenshot. A task that took ~10 tool calls with raw pyautogui takes 2.

## Option A: MCP tools (preferred)

Register once, for every project (from the repo root, inside its venv):

```
python -m venv .venv
.venv\Scripts\pip install -e .[ai]            # Linux/macOS: .venv/bin/pip
.venv\Scripts\python -m automonkey.ai install-claude
```

`install-claude` copies the visual-testing skill into the Claude Code config folder and
runs `claude mcp add --scope user automonkey -- <venv python> <repo>/automonkey/ai/mcp_launch.py`.
(The repo's own `.mcp.json` also registers the server for sessions started in this repo.)

| Tool | Use it for |
|---|---|
| `act(script, screenshot=True, grid=0)` | Many steps at once; returns the log, what changed on screen, and a screenshot |
| `screenshot(grid=0)` | Just looking |
| `zoom(x, y, width, height, grid=0)` | Reading small text, aiming precisely |
| `windows()` | Open windows: id, title, process, bounds |
| `controls(window)` | Every interactive control with its click point, DISABLED/toggle state |
| `find_text(text)`, `read_text(...)` | OCR in the active window (needs tesseract) |
| `history(n)` | The scripts you ran today, as .amk text, to save a bug's steps |
| `replay(path)` | Run a saved .amk regression script; PASSED/FAILED + failure screenshot |

## Option B: shell only

```
.venv\Scripts\python -m automonkey.ai do "launch notepad; type hello"   # log + screenshot path
.venv\Scripts\python -m automonkey.ai --grid 100 shot
.venv\Scripts\python -m automonkey.ai --out C:\tmp\z.png zoom 400 280 480 60
.venv\Scripts\python -m automonkey.ai windows
.venv\Scripts\python -m automonkey.ai controls "My App"
.venv\Scripts\python -m automonkey.ai replay tests\ui\*.amk          # exit code 1 if any fails
```

Open the printed screenshot path with the Read tool. Options such as `--out` and
`--grid` go before the sub-command.

## The action script

One command per line, or `;`-separated (`\;` is a literal semicolon); `#` starts a
comment line. The full list is in the `act` tool description and in
`skills/visual-testing/references/automonkey.md`. The most used:

```
click X Y [left|right|middle] [N]   dclick X Y   rclick X Y   move X Y
drag X1 Y1 X2 Y2 [button]           stroke X1 Y1 X2 Y2 ...    scroll N [X Y]
type TEXT        key K [K...]       hotkey ctrl+shift+t       keydown ctrl / keyup ctrl
launch COMMAND   focus WINDOW       maximize [WINDOW]         close WINDOW
click_control NAME [in WINDOW]      drag_control A to B       tab_order N   clipped
expect_text TEXT    expect_window TITLE    expect_focus NAME    expect_order A, B, C
stable [T]       wait S             save PATH                 finally:  (cleanup that always runs)
```

A failed step stops the script and says which one failed and how many were skipped;
steps after `finally:` still run.

## Rules that make it fast and safe

1. **Coordinates are pixels of the latest screenshot you were shown.** Don't convert them.
2. **Prefer names to pixels.** `controls` gives every control's click point;
   `click_control Save` keeps working when the layout moves.
3. **Batch.** Put every step you're sure about into one `act`; stop to look only when
   the next step depends on what appears.
4. **Read the text summary before the image.** `screen did NOT change` usually means the
   click missed or the window didn't have focus; `region x=.. y=..` says where to look.
5. **`screenshot=false`** when you don't need to look.
6. **Keyboard beats hunting:** `hotkey ctrl+l`, `key tab`, `key escape`, shortcuts.
7. **Don't `wait N` for loading;** use `stable`, `change`, or an `expect_*` (they retry 3 s).
8. **Never type into a window you didn't open.** `launch` stops when it got an
   already-open window back (single-instance apps); open a fresh document first.
9. **Text checks read the active window only** (`screen:` prefix for the whole screen) -
   otherwise your own terminal, showing the script, can match.
10. The red ring in screenshots is the mouse pointer. Pushing the real mouse into a screen
    corner aborts everything (fail-safe): if that happens, the user wants control back.

## Windows notes

- Mouse input goes through `SendInput` with dense, human-like moves, so hover, drags,
  splitters, drag-and-drop and drawing reach every app (WinUI/UWP, Qt, egui, Flutter, Win32).
- The process is per-monitor DPI aware: coordinates are right at 125%/150% scaling.
  Several monitors: `monitor 1` switches screenshots and clicks to monitor 1.
- `focus` verifies the window really is in front. An **elevated** (administrator) app can't
  receive input from a normal process - Windows blocks it; run the app non-elevated.
- `controls` uses UI Automation: Qt, egui (AccessKit), Flutter, WinUI, Win32, WinForms,
  WPF and Chromium/Electron expose controls; DearPyGui and custom canvases don't (use OCR).
  Open menus and context menus are listed too, with their shortcuts (`Save\tCtrl+S`).
- OCR: `winget install UB-Mannheim.TesseractOCR`; found automatically after install.
- `launch` accepts paths (`launch C:\Apps\my app.exe`), Store app aliases (`launch
  mspaint`), and `explorer shell:AppsFolder\<AppID>` (find AppIDs with `Get-StartApps`).

## Linux notes (X11, and Wayland via XWayland - e.g. Raspberry Pi labwc)

- **Only X11 windows receive input.** `launch` sets the variables that force apps onto
  X11 (`MOZ_ENABLE_WAYLAND=0`, `GDK_BACKEND=x11`, `QT_QPA_PLATFORM=xcb`,
  `--ozone-platform=x11`). **Start apps with `launch`, not from the desktop.**
- Browsers get a dedicated automation profile in `~/.cache/automonkey/profiles/` (no
  logins), so they don't merge into the user's native-Wayland browser.
- Screenshots use `grim` on Wayland. Wayland-native windows (e.g. your terminal) don't
  appear in `windows()` and can't be focused.
- Controls: `controls`, `click_control`, `drag_control`, `expect_control`, `expect_order`,
  `focused`, `expect_focus`, `tab_order` and `clipped` use AT-SPI. `launch` sets
  `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1` and drops `NO_AT_BRIDGE` so Qt and GTK apps expose
  their tree; GTK also needs `gsettings set org.gnome.desktop.interface
  toolkit-accessibility true`. Closed menus are not listed: open the menu first.
- A script written on Windows runs unchanged: `launch .venv\Scripts\pythonw.exe tests\apps\x.py`
  starts `.venv/bin/python tests/apps/x.py` on Linux.
- OCR: `sudo apt install tesseract-ocr` (`tesseract-ocr-ron` for Romanian diacritics).

## Example: the whole task in 2 calls

```
act("launch notepad; maximize Notepad")
# look at the screenshot, then:
act("type Hello from AutoMonkey; expect_text Hello from AutoMonkey; hotkey ctrl+a; key delete")
```
