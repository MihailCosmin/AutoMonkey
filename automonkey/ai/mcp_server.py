"""MCP server exposing AutoMonkey to Claude (or any MCP client).

The repo's .mcp.json starts it through mcp_launch.py, which finds the venv on any OS.
Register it by hand with Claude Code (from the repo root):
    claude mcp add automonkey -- python3 "$PWD/automonkey/ai/mcp_launch.py"
"""
from __future__ import annotations

import contextlib
import io
import sys

from mcp.server.mcpserver import Image, MCPServer

from . import act as _act
from . import history as _history
from . import observe, ocr, screen, window_list
from . import replay as _replay
from .script import __doc__ as SCRIPT_DOC
from .. import list_controls as _list_controls

INSTRUCTIONS = f"""Control this computer's screen, mouse and keyboard.

Workflow: call `act` with a whole script of steps; it returns a log, a summary of what
changed on screen, and a fresh screenshot -- you rarely need a separate `screenshot`
call. Batch everything you are confident about into one `act` call; only stop to look
when the next step depends on what appears.

Coordinates are ALWAYS pixels of the latest screenshot image you were shown (the
server converts to real screen pixels). The red ring marks the mouse pointer.

For testing an app the way a user would: `controls(window, interactive_only=True)` lists
every menu, button, link and field with its click point - go through ALL of them.
`tab_order N` checks keyboard navigation, `expect_*` steps turn a script into a check, and
every script you run is recorded: `history` returns them ready to save as a .amk
regression script, `replay` runs a saved one.

Tips: use `url` instead of clicking the address bar; `launch` an app rather than
clicking desktop icons; `zoom` to read small text precisely; `grid=100` overlays
labelled lines when you need exact coordinates; dismiss unexpected popups with
`key escape`. OCR tools (find_text/read_text/click_text) are
{'available' if ocr.available() else 'NOT available yet (tesseract not found); they start working without a restart once it is installed'}.

Action script language:
{SCRIPT_DOC}"""

mcp = MCPServer("automonkey", instructions=INSTRUCTIONS)


def _img(pil) -> Image:
    return Image(data=screen.to_png(pil), format="png")


@mcp.tool()
def act(script: str, screenshot: bool = True, grid: int = 0) -> list:
    """Run an action script (one command per line or ';'-separated), wait for the screen to
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
    Set screenshot=false when you don't need to look (saves tokens); grid=100 adds a grid."""
    text, img = _act(script, screenshot=screenshot, grid=grid)
    return [text, _img(img)] if img is not None else [text]


@mcp.tool()
def screenshot(grid: int = 0) -> list:
    """Take a screenshot. grid=N overlays labelled lines every N pixels for precise coordinates."""
    text, img = observe(grid=grid)
    return [text, _img(img)]


@mcp.tool()
def zoom(x: int, y: int, width: int, height: int, grid: int = 0) -> list:
    """Enlarged full-resolution view of a screenshot region (screenshot coordinates), for small
    text or precise targeting. Grid labels, if requested, use the same screenshot coordinates."""
    return [f"zoom of x={x}..{x + width} y={y}..{y + height}", _img(screen.zoom(x, y, width, height, grid))]


@mcp.tool()
def windows() -> str:
    """List open windows ('*' = active) with ids, titles and their screenshot-coordinate bounds."""
    return window_list()


@mcp.tool()
def list_controls(window: str, depth: int = None) -> str:
    """List a window's controls via the OS accessibility tree (pywinauto on Windows,
    AT-SPI on Linux; not implemented on macOS yet) - role, name and the dict to pass as
    `control` to click/type/etc. Use this instead of screenshots/OCR when the app exposes
    an accessibility tree (most GTK/Qt/native apps do; Electron needs
    --force-renderer-accessibility, canvas-drawn UIs don't expose one at all).

    window: title of the top-level window, regex matched anywhere in the title.
    depth: how many levels deep to go (default: all).
    On Windows prefer `controls`, which is shorter and gives click points."""
    # pywinauto prints the tree; stdout is the MCP protocol stream, so capture it.
    with contextlib.redirect_stdout(io.StringIO()):
        return _list_controls(window, depth)


@mcp.tool()
def controls(window: str, interactive_only: bool = True, depth: int = None, max_items: int = 400) -> str:
    """Every control of a window from the accessibility tree, with the click point of each
    in screenshot coordinates, DISABLED / toggle states, and automation ids (Windows).

    Use it to test COMPLETELY: list the interactive controls (menus, buttons, links, fields,
    tabs, list items), then exercise each one with `act` (click_control NAME, or click X Y).
    Menus only show their items while open: open the menu, then call this again.
    window: title substring, process name (e.g. "notepad.exe") or window id."""
    from . import controls as _controls
    if sys.platform != "win32":
        with contextlib.redirect_stdout(io.StringIO()):
            return _list_controls(window, depth)
    return _controls.tree(window, depth=depth, interactive_only=interactive_only, max_items=max_items)


@mcp.tool()
def replay(path: str) -> list:
    """Run a saved .amk regression script (action-script steps, '#' comments, expect_* checks).
    Returns PASSED/FAILED with the step log; on failure also a screenshot, and the
    full-resolution screen is saved next to the script as <name>.failure.png."""
    ok, log, img = _replay(path)
    return [log, _img(img)] if img is not None else [log]


@mcp.tool()
def history(n: int = 20) -> str:
    """The last n action scripts run today (with ok/FAILED), as .amk text. Copy the steps
    that reproduce a bug into a regression file (add expect_* checks), then `replay` it."""
    return _history(n)


@mcp.tool()
def find_text(text: str, whole_screen: bool = False) -> str:
    """Locate text via OCR in the active window (whole_screen=true: everywhere, which also
    matches text in other windows, e.g. a terminal). Returns boxes and click points in
    screenshot coordinates."""
    from .script import _text_scope
    query, region, where = _text_scope(("screen: " if whole_screen else "") + text)
    hits = ocr.find_text(query, region=region)
    if not hits:
        return f"{text!r} not found {where}"
    return "\n".join(f"{h['text']!r} click at {h['cx']},{h['cy']} (box x={h['x']} y={h['y']} w={h['w']} h={h['h']})"
                     for h in hits[:10])


@mcp.tool()
def read_text(x: int = 0, y: int = 0, width: int = 0, height: int = 0) -> str:
    """OCR the screen (or a region in screenshot coordinates) and return the text. Cheaper than
    a screenshot when you only need to read."""
    return ocr.read_text(x, y, width, height) or "(no text found)"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
