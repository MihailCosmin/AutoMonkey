# AutoMonkey for Claude

Instructions for Claude Haiku 5.5 (or any Claude model) controlling this computer graphically with AutoMonkey's AI layer (`automonkey/ai/`).

## Why the AI layer exists

Raw pyautogui costs about 3 tool calls per step (act, screenshot, look at the image), and you have to guess how long to wait and convert coordinates by hand. The AI layer folds all of that into a single call. The same task (open Firefox, go to google.ro, type `betano.ro`) took about 10 tool calls with raw pyautogui and takes **2** with the AI layer.

## Option A: MCP tools (preferred)

The repo's `.mcp.json` registers the `automonkey` MCP server. Approve it when Claude Code asks. If it isn't registered, run this from the repo root:

```bash
claude mcp add automonkey -- "$PWD/.venv/bin/python" -m automonkey.ai.mcp_server
```

Install the dependency first: `.venv/bin/pip install "mcp>=2"`.

| Tool | Use it for |
|---|---|
| `act(script, screenshot=True, grid=0)` | Running many steps, waiting for the screen to settle, then getting the log, what changed, and a screenshot inline |
| `screenshot(grid=0)` | Just looking |
| `zoom(x, y, width, height, grid=0)` | Reading small text, or aiming precisely |
| `windows()` | Seeing open windows, their ids and where they are |
| `find_text(text)`, `read_text(...)` | OCR (needs tesseract) |

## Option B: shell only

Run the same features from Bash:

```bash
.venv/bin/python -m automonkey.ai do "launch firefox; maximize; url google.ro"   # prints log + screenshot path
.venv/bin/python -m automonkey.ai --grid 100 shot
.venv/bin/python -m automonkey.ai zoom 400 280 480 60
.venv/bin/python -m automonkey.ai windows
```

Then open the printed screenshot path with the Read tool. Use `--out` to save it in your scratchpad.

## The action script

Put one command per line, or separate commands with `;`. Write `\;` for a literal semicolon.

```
click X Y [left|right|middle] [N]   dclick X Y   rclick X Y   move X Y   drag X1 Y1 X2 Y2
scroll N [X Y]        (N>0 up, N<0 down)
type TEXT             (non-ASCII such as ă ș is pasted automatically)
key K [K...]          hotkey ctrl+shift+t
wait SECONDS          stable [TIMEOUT]       change [TIMEOUT]
url ADDRESS           focus the address bar, type, Enter, wait for the page to load
launch COMMAND        start the app as an X11 window and wait for it to appear
focus WINDOW          maximize [WINDOW]      close WINDOW   (match on title or class)
click_text TEXT       wait_text TEXT         (OCR)
click_image PATH      (template matching)
```

The script stops at the first failing step and tells you which one failed and how many steps it skipped.

## Rules that make it fast

1. **Coordinates are always pixels of the latest screenshot you were shown.** Don't convert them. The server maps them to the real screen.
2. **Batch.** Put every step you're sure about into a single `act` call. Stop to look only when the next step depends on what appears.
   - Good: `launch firefox; maximize; url google.ro; key escape`
   - Bad: four separate calls.
3. **Read the text summary before the image.**
   - `screen did NOT change` usually means the click missed, or the window didn't have focus.
   - `screen changed: 3% ... region x=411..869 y=290..600` tells you where to look.
4. **Pass `screenshot=false`** when you don't need to see the result, such as after closing a window. It saves tokens.
5. **Prefer keyboard actions over hunting for things to click:** `url`, `hotkey ctrl+l`, `key tab`, `key escape`, `hotkey ctrl+f`.
6. **Don't use `wait N` for loading.** Use `stable`, or `change` followed by `stable`. `url` and `launch` already wait.
7. **For exact coordinates**, use `grid=100`. For tiny targets, `zoom` the area with `grid=20`. The grid labels are in the same coordinates you click with.
8. **The red ring in screenshots is the mouse pointer** (real screenshots don't show the cursor).

## Environment notes (Raspberry Pi, Wayland/labwc)

- **Only X11 windows receive input.** pyautogui sends input through XWayland. `launch` sets the variables that force apps onto X11 (`MOZ_ENABLE_WAYLAND=0`, `GDK_BACKEND=x11`, `QT_QPA_PLATFORM=xcb`, and `--ozone-platform=x11` for Chromium-based apps). **Start apps with `launch`, not from the desktop.**
- **Browsers get their own automation profile.** If the user's Firefox or Chromium is already open as a native Wayland window, a plain `firefox` launch would be handed to it and come out uncontrollable. So `launch` uses a dedicated profile in `~/.cache/automonkey/profiles/`. For Firefox, that profile also turns off first-run tabs and the translation popup. It has no logins or cookies from the user's normal browser.
- **Screenshots use `grim`.** The layer captures at full resolution and shrinks the image in Python, because `grim -s` is about 3x slower.
- **Some windows are invisible to the tools.** Wayland-native windows, such as the terminal you're running in, don't show up in `windows()` and can't be focused. Don't click into them by accident.
- **Firefox's translation popup** shows up on Romanian pages, sometimes while you type. Use `key escape`.
- **The pyautogui fail-safe** stops a script if the mouse touches a screen corner. Avoid clicking exact corners.
- **OCR needs tesseract:** `sudo apt install tesseract-ocr tesseract-ocr-ron`. Without it, use coordinates and `zoom`.

## Example: the whole task in 2 calls

```
act("launch firefox --new-window about:blank; maximize; url google.ro; key escape")
# look at the screenshot: the search box is at about 640,304
act("click 640 304; hotkey ctrl+a; type betano.ro; wait 0.5; key escape")
```
