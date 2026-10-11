"""AI-friendly layer over AutoMonkey: act + observe in a single call.

    from automonkey.ai import act, observe
    text, img = act("launch firefox; maximize; url google.ro; type betano.ro")

All coordinates are pixels of the screenshot the AI was shown.
"""
from __future__ import annotations

from PIL import Image

from . import ocr, screen, windows
from .script import run, split_script


def _context() -> str:
    v = screen.view()
    try:
        w = windows.active_window()
        active = f"active window: {w['title']!r}"
    except Exception:
        active = "active window: unknown"
    return f"{v.describe()}; {active}"


def observe(grid: int = 0, max_side: int = screen.DEFAULT_MAX_SIDE) -> tuple[str, Image.Image]:
    img = screen.shot(grid=grid, max_side=max_side)
    return _context(), img


def act(script: str, screenshot: bool = True, grid: int = 0, settle: bool = True) -> tuple[str, Image.Image | None]:
    """Run an action script, then report what happened (and show the screen)."""
    before = screen.grab()
    log, ok = run(script, settle=settle)
    after = screen.grab()
    img = screen.shot(grid=grid, full=after) if screenshot else None
    lines = log + [screen.diff_summary(before, after), _context()]
    if not ok:
        lines.insert(0, "STOPPED AT A FAILED STEP")
    return "\n".join(lines), img


def window_list() -> str:
    v = screen.view()
    out = []
    for w in windows.list_windows():
        x, y = v.to_image(w["x"], w["y"])
        r, b = v.to_image(w["x"] + w["w"], w["y"] + w["h"])
        out.append(f"{'*' if w['active'] else ' '} {w['id']:>10}  {w['title']!r}  [{w['wm_class']}]  "
                   f"x={x}..{r} y={y}..{b}")
    return "\n".join(out) or "no windows"


__all__ = ["act", "observe", "window_list", "ocr", "screen", "windows", "run", "split_script"]
