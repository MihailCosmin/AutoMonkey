# AI tips for driving desktop apps with AutoMonkey

Field notes from automating **Windows 11 Paint** (`mspaint`) with the AI layer
(`automonkey/ai/`). The Paint specifics are examples; every rule below is written so it
applies to other GUI programs too — CAD packages, Office, browsers, ERP clients.

Companion docs: `automonkey_for_claude.md` (the action-script reference and MCP tools),
`README.md`.

---

## 1. The one rule that matters: input must enter the input stack

**`SetCursorPos` is invisible to modern applications. Use `SendInput` / `mouse_event`.**

`pyautogui.moveTo()` — and therefore AutoMonkey's `move`, `drag` and `path` — moves the
cursor with `SetCursorPos`. That call repositions the cursor but **never enters the
Windows input stack**, so it produces *no input event at all*. A low-level mouse hook
(`WH_MOUSE_LL`) does not even see it, and neither does the app.

This was measured, not guessed. With a hook running:

| Action | Events seen by the hook |
|---|---|
| human drawing by hand | 1,743 move events |
| `pyautogui.moveTo(...)` x N | **0 events** |
| `mouse_event(MOVE\|ABSOLUTE, ...)` x N | N events, `injected=1` |

### Why the symptom is so confusing

Modern **WinUI 3 / UWP / XAML apps** (Windows 11 Paint, Notepad, Snipping Tool, Settings)
build strokes, selections and drags from **pointer input**. If no move events arrive, the
app only sees the position that happens to be current when the next *real* event lands.
So we got:

| Path requested | What actually appeared |
|---|---|
| open straight drag | a straight line — **looks like success** |
| square, zigzag | a single dot at the press point |
| circle (start == end) | a single dot |
| rectangle / any closed shape | a single dot |

**Do not treat a straight-line result as proof that the pipeline works.** A straight line
is the one shape that cannot fail, because "press position → final position" *is* a straight
line. Every false "it works" reading in this project came from that.

### Note: clicks are not the problem, drags are

`pyautogui.click()` already goes through `mouse_event`, which is why **clicking buttons,
menus and tool icons worked from the very first try while drags silently did nothing**.
When a GUI automation *clicks fine but drags/paints badly*, suspect the move path, not
your coordinates.

### The fix

```python
import ctypes, time

u = ctypes.windll.user32
MOVE_ABS = 0x0001 | 0x8000        # MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
DOWN, UP = 0x0002, 0x0004
W, H = 1920, 1080                 # PRIMARY monitor size

def emove(x, y):
    u.mouse_event(MOVE_ABS, int(round(x) * 65535 // (W - 1)),
                             int(round(y) * 65535 // (H - 1)), 0, 0)

emove(x0, y0);            time.sleep(0.30)
u.mouse_event(DOWN, 0, 0, 0, 0); time.sleep(0.25)
for x, y in path[1:]:
    emove(x, y);          time.sleep(0.008)   # ~125 events/s
time.sleep(0.25)
u.mouse_event(UP, 0, 0, 0, 0)
```

- Absolute coordinates are normalised **over the primary monitor** (`65535/(W-1)`). This
  is a real trap on multi-monitor machines: here the virtual desktop was 5760x1200 while
  the primary was 1920x1080, so anything on a second monitor needs its own handling.
- `SendInput` (via ctypes) is equivalent and slightly more robust; `mouse_event` is
  deprecated but universally available.

---

## 2. Find out how the app wants its input before tuning constants

Don't guess step size and delays. **Record a human doing the task once, then copy the
numbers.** Measured while a person drew circles freehand in Paint:

| Property | Measured value |
|---|---|
| event rate | ~100 move events/s |
| step between events | median **2.2 px**, min 0, max 7 px |
| stroke duration | 2.6 – 3.6 s per circle |
| radius they drew | ~108 px |

Our winning synthetic parameters were close to that: **~1 px per event at 8 ms (~125 ev/s)**.
For reference, the failing attempts used 12–50 ms spacing with 3–35 px steps — those
numbers *felt* reasonable and were simply the wrong thing to be tuning: the moves never
reached the app regardless of pacing.

**Rule of thumb:** step 1–3 px, 5–10 ms between events. Finer than the app's own input
sampling is wasted; coarser produces visible polygon edges on curves.

---

## 3. Launching an application

Prefer the AI layer's verb so it waits for the window and focuses it:

```
launch mspaint; wait 3; maximize; wait 1.5
```

- `launch COMMAND` starts the process, waits for a window, and focuses it
  (`automonkey/ai/windows.py: launch()` + `focus()`). `maximize` then fixes the geometry
  so canvas coordinates are stable and predictable.
- **Verify the app is actually running before querying it.** `get_window("Paint")` raises
  `pywinauto.timings.TimeoutError` if the window doesn't exist — which is what happens
  when the user closed Paint between runs. Launch-if-missing at the start of every script:

  ```python
  def ensure_paint():
      for _ in range(3):
          ws = [w for w in gw.getAllWindows() if "Paint" in w.title and w.visible]
          if ws:
              return ws[0]
          amc.act("launch mspaint; wait 3; maximize; wait 1.5", screenshot=False)
          time.sleep(2)
      raise SystemExit("app could not be started")
  ```

- Match windows on a **substring that survives renaming**. The title here was
  `Fără titlu - Paint` ("Untitled"); after any save it changes. Match `"Paint"`, not the
  full title. For other apps, prefer matching on process name or window class.
- Common launch commands: `mspaint`, `notepad`, `calc`, `explorer <folder>`, `chrome <url>`.
  For anything unusual, `Get-StartApps` (PowerShell) lists the exact AppID.
- **Start the app through the automation layer, not by hand**, so it is launched from the
  same session/desktop and is therefore controllable. (Critical on Wayland — see
  `automonkey_for_claude.md` — and good hygiene on Windows when running elevated vs. not.)

---

## 4. Selecting a tool (and not deselecting it again)

The Paint pencil is a **toggle button**. Its UI Automation control type is `Button`, its
name is `Creion` (Romanian UI), and **clicking it while it is already active turns it
off**. A blind "click the pencil to be safe" is therefore a bug, not a safety measure.

**Always read the state, then click only if it is off:**

```python
TOOLS = ("Creion", "Text", "Radieră", "Umplere", "Selector de culoare", "Lupă")

def pencil_on():
    w = get_window("Paint")
    tools, colours = [], []
    for d in w.descendants():
        try:
            nm = (d.element_info.name or "").strip()
            ct = d.element_info.control_type
        except Exception:
            continue
        if ct == "Button" and nm in TOOLS:
            if d.get_toggle_state():
                tools.append(nm)
        if ct == "RadioButton" and nm.startswith("Culoare"):
            colours.append(nm)
    return tools, colours

on, colour = pencil_on()
if "Creion" not in on:
    amc.act("focus Paint; wait 0.4; click 173 59; wait 0.8", screenshot=False)
    on, colour = pencil_on()
if "Creion" not in on:
    raise SystemExit("pencil not selected - aborting")     # never draw blind
```

Generalised:

- **Read state before acting.** `get_toggle_state()` for toggles, control type + name +
  rect for buttons. Assert after every state change, and abort loudly if the assert fails.
- **One click at a time, then re-read.** Two fast clicks on a toggle net out to nothing.
- **Use the name, but don't trust the language.** Names are localised (`Creion`, not
  "Pencil"); the coordinate fallback is language-independent but fragile. Where the app
  offers a keyboard shortcut, prefer it — shortcuts bypass the palette entirely and are
  the most stable tool selection method across versions and locales.
- **Confirm the colour too.** `Culoare 1: Negru` / `Culoare 2: Alb` tells you the pencil is
  black. Drawing white-on-white produces a *perfect artefact that is invisible* — a classic
  "why is nothing happening" trap.

---

## 5. Resetting state before you draw

A repeatable run needs a known canvas. The working sequence was:

```
focus Paint; hotkey ctrl+a; key delete; key escape
```

Two traps here, both generalise:

1. **`Ctrl+A` silently switches Paint to the Select tool.** Clearing the canvas therefore
   also changes the active tool, and the next stroke becomes a rubber-band *selection*
   instead of ink. **After any reset, re-select the tool and verify it.**
2. **`Esc` deselects but does not restore the previous tool.**

General rule: **a "reset" step in a GUI is never neutral.** Treat it as a state change,
and re-establish every piece of state you depend on (tool, colour, layer, active document,
zoom) afterwards rather than assuming it survived.

---

## 6. Drawing: analytic geometry, not hand tracing

There are two levels of "draw a circle", and they are not equivalent:

- **Replaying a recorded human trace** reproduces *that person's* wobble. It proves the
  input path works, and nothing about your ability to draw.
- **Generating the path analytically** produces a true circle and is what should ship.

```python
import numpy as np

CX, CY, R = 960, 583, 180          # canvas centre, drawn radius
STEPS_PER_PX = 1.0
N = int(2 * np.pi * R * STEPS_PER_PX)
DT = 0.008

path = [(CX + R*np.cos(t), CY + R*np.sin(t))
        for t in (2*np.pi*i/N for i in range(N + 1))]
# close seamlessly: overlap ~2 degrees so the start/end join has no nick
path += [(CX + R*np.cos(t), CY + R*np.sin(t))
         for t in (2*np.pi*k/N for k in range(1, 30))]
```

Measured result in Paint (pencil, black, 1,160 injected points, 13.5 s):

| Metric | Result |
|---|---|
| centre | (960, 583) — exactly on target |
| bbox | 360 x 360 |
| radius | min 179.33, max 180.65, mean **180.01** (target 180) |
| radius sd | **0.30 px** |
| circularity (sd/mean) | **0.0016** |
| angular bins covered | **360/360**, largest gap **0 deg** |
| max median-radius deviation | **0.41 px** |

For comparison, human freehand in the same tool: sd/mean **0.071** — about 44x worse.

Other generalisable points:

- **Plan the geometry for the canvas**, and verify it fits the canvas rect before drawing
  (a circle at a canvas corner is clipped, and clipping looks like a drawing bug).
- **Close curves with a small overlap** so antialiasing doesn't leave a visible nick.
- **Draw tangentially, avoid long straight jumps inside a stroke** — a 300 px jump in a
  single event is where "only endpoints survive" artifacts are most visible.
- **Prefer one continuous stroke.** Many small strokes leave seams and multiply the
  opportunity for state/tool changes between them.

---

## 7. Focus: the silent killer

Even with correct injection, input goes to the **foreground window**. Verify, don't assume:

```python
def force_focus(hwnd):
    if u.GetForegroundWindow() == hwnd:
        return True
    fg = u.GetForegroundWindow()
    t_fg = u.GetWindowThreadProcessId(fg, None)
    t_me = ctypes.windll.kernel32.GetCurrentThreadId()
    u.AttachThreadInput(t_me, t_fg, True)     # lets a background process take focus
    u.ShowWindow(hwnd, 9)                     # SW_RESTORE
    u.SetForegroundWindow(hwnd)
    u.BringWindowToTop(hwnd)
    u.AttachThreadInput(t_me, t_fg, False)
    time.sleep(0.5)
    return u.GetForegroundWindow() == hwnd
```

- `SetForegroundWindow` from a non-foreground process **fails silently**; the
  `AttachThreadInput` dance is the standard workaround.
- **Check the foreground immediately before the first injected event — and again if the
  stroke is long.** Observed here: `focus Paint` reported success, then the foreground was
  `Hermes` a second later, and the whole drag went into the wrong window (it produced
  *nothing at all* on the canvas, which reads exactly like "drawing is broken").
- **Abort if the check fails.** Never fire a stroke into whatever happens to be focused.
- `pygetwindow`'s `activate()` raises `PyGetWindowException` carrying Windows error **0**
  (i.e. *success*) — wrap it in try/except and verify with `GetForegroundWindow()` rather
  than treating the exception as a failure.

---

## 8. Coordinate systems — three of them, and they are not interchangeable

Getting these confused produces "off by a scale factor" bugs that look like broken apps.

| Space | Example here | Notes |
|---|---|---|
| Real screen (injection space) | 1920 x 1080, primary monitor | what `mouse_event` absolute uses |
| Virtual desktop | 5760 x 1200 | multi-monitor; each monitor has an offset |
| Screenshot shown to the AI | 1280 x 720 | **downscaled**; scale = `W_screen / W_image` |

- The AI layer gives coordinates **in pixels of the latest screenshot**. If you then feed
  those numbers to raw `mouse_event`, **multiply by the scale factor first** (here 1.5).
  AutoMonkey's own verbs do the mapping for you; hand-rolled ctypes does not.
- DPI: check `GetDpiForSystem()` (96 here = 100%). On a scaled display an unaware process
  gets virtualised coordinates and everything drifts proportionally.
- **For CAD and other canvas apps this matters most**: on-screen pixels are *viewport*
  coordinates, not model coordinates. Any real precision must come from typed coordinates
  or object snaps (§10), never from pixel dragging.

---

## 9. Recording and logging, for future debugging

### 9.1 Log every injected step

Write one JSON object per line (JSONL) as you go — it survives a crash, and you can read it
while the process is still running. Log the intent *and* the actual injected value:

```json
{"t": 0.412, "e": "move", "x": 1096, "y": 354, "inj": 1, "want": [1096, 354]}
{"t": 0.680, "e": "ldown", "x": 1096, "y": 354, "inj": 1, "fg": "Fără titlu - Paint"}
```

Include: timestamp, event kind, coordinates, the injected flag, and the foreground window
at each button event. That single file answers "did it go where I meant?" and "did it go to
the right window?" without re-running anything.

### 9.2 Record real input, to learn the app's expectations

A low-level hook captures *hardware* input (what a human really does) and your own
synthetic input, and the `injected` flag tells them apart. This is the tool that cracked
this problem: it showed that human moves arrive and `SetCursorPos` moves **never arrive**.

```python
import ctypes, ctypes.wintypes as wt, json, time

u = ctypes.windll.user32
WH_MOUSE_LL, PM_REMOVE, LLMHF_INJECTED = 14, 1, 0x00000001
NAMES = {0x0200: "move", 0x0201: "ldown", 0x0202: "lup",
         0x0204: "rdown", 0x0205: "rup", 0x020A: "wheel"}

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                              ctypes.c_ssize_t, ctypes.c_ssize_t)
u.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                             ctypes.c_ssize_t, ctypes.c_ssize_t]

def proc(nCode, wParam, lParam):
    if nCode == 0:
        ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        msg = int(wParam)
        f.write(json.dumps({"t": round(time.time() - t0, 4),
                            "e": NAMES.get(msg, hex(msg)),
                            "x": ms.pt.x, "y": ms.pt.y,
                            "inj": 1 if (ms.flags & LLMHF_INJECTED) else 0}) + "\n")
    return u.CallNextHookEx(None, nCode, wParam, lParam)

cb = HOOKPROC(proc)                       # keep this reference alive!
hook = u.SetWindowsHookExW(WH_MOUSE_LL, cb, None, 0)   # hMod MUST be None
```

Hook gotchas (all hit in practice):

- **`hMod` must be `None`/NULL** for `WH_MOUSE_LL`. Passing `GetModuleHandleW(None)` fails
  with error **126** (`ERROR_MOD_NOT_FOUND`).
- **Keep a Python reference to the callback** or it is garbage-collected mid-recording.
- **Pump messages with `PeekMessageW` in a loop** (not blocking `GetMessageW`) so a
  duration cap or stop-file can be honoured. The hook does **not** steal focus.
- **Declare pointer-sized types.** With 32-bit `wintypes.LPARAM` the callback floods
  `OverflowError: int too long to convert`; ctypes then returns 0, and **a hook that
  returns 0 swallows the mouse event**. Set `CallNextHookEx.argtypes` explicitly.
- Log *before* chaining to `CallNextHookEx`, so a crashing hook still leaves a usable
  recording.
- Run it as a **background process**, writing to a workspace file, and flush periodically.

### 9.3 Read the recording like a scientist

```python
# split into strokes: ldown -> lup, keeping only those that landed on the target window
strokes, cur = [], None
for e in ev:
    if e.get("e") == "ldown":
        cur = {"t0": e["t"], "fg": e.get("fg"), "pts": [(e["x"], e["y"])], "inj": e["inj"]}
    elif e.get("e") == "move" and cur is not None:
        cur["pts"].append((e["x"], e["y"]))
    elif e.get("e") == "lup" and cur is not None:
        cur["t1"] = e["t"]; strokes.append(cur); cur = None
```

Then per stroke print: point count, duration, **event rate**, bbox, start/end gap,
distance from the centroid (min/max/mean/sd), step-size distribution, and `inj`. Those
numbers tell you both how the app wants input (§2) and whether your own injection behaved.

But the decisive question is **which window each stroke landed on** — log the foreground
window on button events and group by it, or you will analyse strokes that never reached
the app.

### 9.4 Capture before/after and verify with pixels, never with return codes

An action script returning `ok` proves nothing about what appeared on screen. The standard
loop:

1. screenshot → 2. act → 3. screenshot → 4. **diff the region** → 5. fit the result.

This project generated several false positives from a diff that included the taskbar clock
("282 px changed!" was entirely the clock). So: diff a **tight region inside the canvas**,
and out of the target window, and prefer a *shape metric* over a raw pixel count.

For a circle, the metrics that actually settle it:

```python
a = np.asarray(screenshot.convert("L"), dtype=np.int16)
dark = a[y0:y1, x0:x1] < 110            # ink in the canvas region
ys, xs = np.nonzero(dark)
cx, cy = xs.mean(), ys.mean()
rad = np.hypot(xs - cx, ys - cy)
print("circularity", rad.std() / rad.mean())          # ~0.002 synthetic, ~0.07 freehand
bins = {int(np.degrees(np.arctan2(y - cy, x - cx)) % 360) for x, y in zip(xs, ys)}
print("angular coverage", len(bins) / 360)             # 1.0 = closed, no gaps
```

Plus an **ASCII render of the region** (one character per NxN block) — the cheapest way to
*see* the result, confirm a ring versus a dot, and spot a clipping problem, without images.

---

## 10. Applying this to other programs (CAD, Office, browsers)

The Windows/input rules above are universal. The per-app part is *state*:

| Concern | Paint | CAD (AutoCAD / BricsCAD / FreeCAD) | Office / browsers |
|---|---|---|---|
| Launch | `mspaint` | heavy apps: wait for the splash to clear, then for the main window | `chrome <url>`; `launch` normally waits |
| Tool selection | toggle buttons in the ribbon; `get_toggle_state()` | modal command line + toolbars; **prefer typing the command** (`LINE`, `CIRCLE`) | ribbons/tabs; prefer shortcuts (Ctrl+B, Ctrl+K) |
| State to re-establish after a reset | active tool, colour 1/2 | active command, layer, current UCS, ortho/polar, osnap, selection set | document, active sheet/cell, cursor position |
| "Draw a shape" | inject a dense stroke | **type exact coordinates**; snaps beat pixels | type into a cell; don't drag-select |
| Modal blockers | colour dialog, save prompt | command prompts, "select object:" waits, model/paper space switches | print dialogs, auth prompts, cookie banners |
| Undo | `Ctrl+Z` | `Ctrl+Z` per command; `U` / `UNDO` | `Ctrl+Z` |
| Precision | pixels are the unit | pixels are a *viewport*; model units need typed input | exact values by typing |

Rules of thumb that transfer:

- **Prefer a data path over a pixel path.** If the app accepts typed coordinates, a
  command line, a script, a plugin API or a file import, use that and treat pixel input as
  the fallback. It is faster, exact, and immune to zoom, pan, DPI and theme changes.
- **Pixel dragging is for freehand.** For anything with a defined geometry, generate the
  path mathematically (§6) or type it.
- **After any modal dialog, everything you knew about state is suspect.** Re-assert tool,
  colour/layer, and focus before the next stroke.
- **Escape is your friend, but it also changes state.** `Esc` cancels commands and clears
  selections — usually what you want, never assumed.
- **Verify with shape metrics** (§9.4), because these apps happily accept input and produce
  something subtly different from what you asked for.
- **Build idempotent step sequences.** A run should be repeatable from an unknown starting
  state: ensure app → ensure window → ensure geometry → reset → re-select tool → verify →
  act → verify.

---

## 11. Known bugs / open work in AutoMonkey

1. **`move` / `drag` / `path` use `SetCursorPos` and are therefore invisible to WinUI/UWP/
   XAML apps** (and any app consuming pointer input). Fix: route them through
   `SendInput`/`mouse_event` with ~1–3 px steps, keeping AutoMonkey's existing
   screenshot→screen coordinate scaling. `click` already works because `pyautogui.click`
   uses `mouse_event`. This is the single highest-value fix in the layer.
2. **`focus` can report success while the foreground has already changed.** Return/verify
   `GetForegroundWindow()` and expose the check to callers.
3. **`get_window()` raises `TimeoutError` when the app simply isn't running** — a
   launch-if-missing helper (or a clearer error) would save a debugging cycle.
4. **The action-script layer has no documented verb for injecting a dense stroke.** A
   `stroke X Y X Y ...` verb backed by `SendInput` (rather than `path`) would make all of
   §1 available from a single script line.

---

## 12. Quick checklist before blaming the app

1. Is the app actually running? (launch-if-missing)
2. Is the correct window **foreground**, verified with `GetForegroundWindow()`?
3. Is the needed **tool toggled on**, read via `get_toggle_state()` — not clicked blindly?
4. Is the drawing **colour visible** against the canvas?
5. Are the moves injected with **`mouse_event`/`SendInput`** — not `SetCursorPos`?
6. Are they **~1–3 px apart at 5–10 ms**, and does the geometry fit inside the canvas?
7. Did the reset step silently **change the tool** (`Ctrl+A` → Select)?
8. Are you verifying with a **shape metric in a tight region**, not a pixel-count over the
   whole screen or a "step ok" return code?
9. Multi-monitor or DPI scaling in play? Recheck §8 before trusting any coordinate.