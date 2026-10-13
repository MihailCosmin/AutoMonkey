"""MCP server exposing AutoMonkey to Claude (or any MCP client).

The repo's .mcp.json starts it through mcp_launch.py, which finds the venv on any OS.
Register it by hand with Claude Code (from the repo root):
    claude mcp add automonkey -- python3 "$PWD/automonkey/ai/mcp_launch.py"
"""
from __future__ import annotations

from mcp.server.mcpserver import Image, MCPServer

from . import act as _act
from . import observe, ocr, screen, window_list
from .script import __doc__ as SCRIPT_DOC

INSTRUCTIONS = f"""Control this computer's screen, mouse and keyboard.

Workflow: call `act` with a whole script of steps; it returns a log, a summary of what
changed on screen, and a fresh screenshot -- you rarely need a separate `screenshot`
call. Batch everything you are confident about into one `act` call; only stop to look
when the next step depends on what appears.

Coordinates are ALWAYS pixels of the latest screenshot image you were shown (the
server converts to real screen pixels). The red ring marks the mouse pointer.

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

    Commands: click X Y [button] [N] | dclick X Y | rclick X Y | move X Y | drag X1 Y1 X2 Y2 |
    scroll N [X Y] | type TEXT | key K [K..] | hotkey ctrl+l | wait S | stable [T] | change [T] |
    url ADDRESS | launch CMD | focus WINDOW | maximize [WINDOW] | close WINDOW |
    click_text TEXT | wait_text TEXT | click_image PATH

    Example: "launch firefox; maximize; url google.ro; click 640 290; type betano.ro"
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
def find_text(text: str) -> str:
    """Locate text on screen via OCR. Returns boxes and click points in screenshot coordinates."""
    hits = ocr.find_text(text)
    if not hits:
        return f"{text!r} not found"
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
