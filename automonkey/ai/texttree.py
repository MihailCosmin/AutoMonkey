"""Text of the visible text controls of a window, read through the accessibility API
instead of OCR: AT-SPI `Atspi.Text` on Linux, UI Automation `TextPattern` on Windows.

Self-drawn text views that expose a Text interface (the micomuXML WYSIWYG view, Qt text
edits, GTK entries and labels, browsers' text nodes) give exact text and exact character
boxes, also for tiny or low-contrast fonts OCR misreads. `find` and `read` return None
when no text control has anything to say, so the caller falls back to OCR.
Boxes are in screenshot pixels, like the OCR path: dict(text, x, y, w, h, cx, cy, exact).
"""
from __future__ import annotations

import sys

from . import screen
from .controls import normalize

MAX_CHARS = 200_000  # per control: the visible range is used when the toolkit can tell it


def _fold(text: str) -> tuple[str, list[int]]:
    """normalize() applied per character, so a match in the folded text maps back to
    offsets of the original: (folded text, original offset of each folded character)."""
    out, idx, space = [], [], True
    for i, ch in enumerate(text):
        n = normalize(ch)
        if not n:
            if ch.isspace():
                n = " "
            else:
                continue
        for c in n:
            if c == " ":
                if space:
                    continue
                space = True
            else:
                space = False
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def _match_offsets(text: str, query: str) -> list[tuple[int, int, bool]]:
    """(start, end, whole control text) offsets of the occurrences of `query` in `text`."""
    q = normalize(query)
    if not q:
        return []
    folded, idx = _fold(text)
    hits, pos = [], folded.find(q)
    while pos >= 0:
        end = pos + len(q) - 1
        hits.append((idx[pos], idx[end] + 1, folded.strip() == q))
        pos = folded.find(q, pos + 1)
    return hits


def _in(rect, box) -> bool:
    x, y, w, h = box
    cx, cy = x + w // 2, y + h // 2
    return rect[0] <= cx < rect[0] + rect[2] and rect[1] <= cy < rect[1] + rect[3]


def _hit(text, x0, y0, x1, y1, exact):
    return dict(text=text, x=x0, y=y0, w=x1 - x0, h=y1 - y0, cx=(x0 + x1) // 2, cy=(y0 + y1) // 2, exact=exact)


# ---- Linux: AT-SPI ------------------------------------------------------------------------

def _atspi_texts(window, region):
    """Yield (Text interface, control rect in image px) of the showing text controls."""
    from . import atspi_tree
    for _level, acc, p in atspi_tree.walk(window):
        if not p["rect"]:
            continue
        try:
            iface = acc.get_text_iface()
        except Exception:
            iface = None
        if iface is None:
            continue
        rect = p["rect"]
        if region and not (rect[0] < region[0] + region[2] and region[0] < rect[0] + rect[2]
                           and rect[1] < region[1] + region[3] and region[1] < rect[1] + rect[3]):
            continue
        yield iface, rect


def _atspi_visible_text(iface, rect) -> tuple[str, int]:
    """(text of the visible part of the control, offset of its first character)."""
    from ..atspi_funcs import _atspi
    Atspi = _atspi()
    v = screen.view()
    try:
        n = Atspi.Text.get_character_count(iface)
    except Exception:
        return "", 0
    if n <= 0:
        return "", 0
    lo, hi = 0, n
    if n > 2000:  # a long document: ask the toolkit which characters are on screen
        try:
            ix, iy = v.to_input(rect[0] + 1, rect[1] + 1)
            jx, jy = v.to_input(rect[0] + rect[2] - 1, rect[1] + rect[3] - 1)
            a = Atspi.Text.get_offset_at_point(iface, ix, iy, Atspi.CoordType.SCREEN)
            b = Atspi.Text.get_offset_at_point(iface, jx, jy, Atspi.CoordType.SCREEN)
            if a >= 0 and b >= a:
                lo, hi = a, min(n, b + 1)
        except Exception:
            pass
    hi = min(hi, lo + MAX_CHARS)
    try:
        return Atspi.Text.get_text(iface, lo, hi) or "", lo
    except Exception:
        return "", 0


def _atspi_box(iface, start, end):
    """Box in image px of characters start..end, cut at the end of the first line."""
    from ..atspi_funcs import _atspi
    Atspi = _atspi()
    v = screen.view()

    def ext(a, b):
        e = Atspi.Text.get_range_extents(iface, a, b, Atspi.CoordType.SCREEN)
        return e.x, e.y, e.width, e.height
    first = ext(start, start + 1)
    x, y, w, h = ext(start, end)
    if first[3] > 0 and h > first[3] * 1.5:  # the match wraps over lines: keep its first line
        last = start + 1
        while last < end and abs(ext(last, last + 1)[1] - first[1]) < max(first[3] // 2, 1):
            last += 1
        x, y, w, h = ext(start, last)
    if w <= 0 or h <= 0:
        return None
    x0, y0 = v.to_image(x, y)
    x1, y1 = v.to_image(x + w, y + h)
    return x0, y0, x1, y1


def _atspi_find(window, query, region):
    hits = []
    for iface, rect in _atspi_texts(window, region):
        text, base = _atspi_visible_text(iface, rect)
        for s, e, whole in _match_offsets(text, query):
            try:
                box = _atspi_box(iface, base + s, base + e)
            except Exception:
                box = None
            if not box:
                continue
            h = _hit(text[s:e], *box, whole)
            b = (h["x"], h["y"], h["w"], h["h"])
            if _in(rect, b) and (not region or _in(region, b)):
                hits.append(h)
    return hits


def _atspi_read(window, region):
    """Text of the visible lines of every text control, top to bottom; lines outside
    `region` (x, y, w, h in image px) are left out."""
    from ..atspi_funcs import _atspi
    Atspi = _atspi()
    v = screen.view()
    blocks = []
    for iface, rect in _atspi_texts(window, region):
        text, base = _atspi_visible_text(iface, rect)
        if not text.strip():
            continue
        lines, pos = [], 0
        for line in text.split("\n"):
            if line.strip():
                keep = True
                if region:
                    try:
                        e = Atspi.Text.get_range_extents(iface, base + pos, base + pos + 1, Atspi.CoordType.SCREEN)
                        x0, y0 = v.to_image(e.x, e.y)
                        keep = e.width > 0 and _in(region, (x0, y0, 1, 1))
                    except Exception:
                        keep = True
                if keep:
                    lines.append(line)
            pos += len(line) + 1
        if lines:
            blocks.append((rect[1], rect[0], "\n".join(lines)))
    blocks.sort(key=lambda b: (b[0], b[1]))
    return "\n".join(b[2] for b in blocks)


# ---- Windows: UI Automation TextPattern (not exercised on a Windows machine yet) ----------

_UIA_TEXT_PATTERN = 10014
_TEXT_TYPES = {"Edit", "Document", "Text"}


def _uia_patterns(window, region):
    from . import controls
    for _level, ei, p in controls.walk(window):
        if p["type"] not in _TEXT_TYPES or not p["rect"]:
            continue
        try:
            import comtypes.gen.UIAutomationClient as uia
            pattern = ei.element.GetCurrentPattern(_UIA_TEXT_PATTERN).QueryInterface(uia.IUIAutomationTextPattern)
        except Exception:
            continue
        yield pattern, p["rect"]


def _uia_rects(rng):
    v = screen.view()
    raw = list(rng.GetBoundingRectangles() or ())
    out = []
    for i in range(0, len(raw) - 3, 4):
        x0, y0 = v.to_image(raw[i], raw[i + 1])
        x1, y1 = v.to_image(raw[i] + raw[i + 2], raw[i + 1] + raw[i + 3])
        out.append((x0, y0, x1, y1))
    return out


def _uia_find(window, query, region):
    hits = []
    for pattern, rect in _uia_patterns(window, region):
        try:
            visible = pattern.GetVisibleRanges()
            for i in range(visible.Length):
                found = visible.GetElement(i).FindText(query, False, True)
                if found is None:
                    continue
                boxes = _uia_rects(found)
                if boxes:
                    h = _hit(found.GetText(-1), *boxes[0], False)
                    if _in(rect, (h["x"], h["y"], h["w"], h["h"])):
                        hits.append(h)
        except Exception:
            continue
    return hits


def _uia_read(window, region):
    blocks = []
    for pattern, rect in _uia_patterns(window, region):
        try:
            visible = pattern.GetVisibleRanges()
            text = "\n".join(visible.GetElement(i).GetText(MAX_CHARS) for i in range(visible.Length))
        except Exception:
            continue
        if text.strip():
            blocks.append((rect[1], rect[0], text))
    blocks.sort(key=lambda b: (b[0], b[1]))
    return "\n".join(b[2] for b in blocks)


# ---- public ------------------------------------------------------------------------------

def find(window, query: str, region: tuple[int, int, int, int] | None = None) -> list[dict] | None:
    """Occurrences of `query` in the text controls of `window`, best match first, or None
    when the platform has no text API, the window has no accessibility tree or no text
    control holds the text (the caller then uses OCR)."""
    if sys.platform not in ("win32", "linux"):
        return None
    try:
        hits = (_uia_find if sys.platform == "win32" else _atspi_find)(window, query, region)
    except Exception:
        return None
    hits.sort(key=lambda h: (not h["exact"], h["y"], h["x"]))
    return hits or None


def read(window, region: tuple[int, int, int, int] | None = None) -> str | None:
    """Visible text of the text controls of `window` (inside `region`), or None for OCR."""
    if sys.platform not in ("win32", "linux"):
        return None
    try:
        return (_uia_read if sys.platform == "win32" else _atspi_read)(window, region) or None
    except Exception:
        return None
