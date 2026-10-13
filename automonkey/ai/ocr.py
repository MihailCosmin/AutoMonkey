"""Optional OCR: find text on screen so the AI can click by label instead of coordinates.

Needs the tesseract binary (Linux: `sudo apt install tesseract-ocr`).
"""
from __future__ import annotations

import shutil

from PIL import Image, ImageOps

from .screen import grab, view


def available() -> bool:
    return shutil.which("tesseract") is not None


def _require():
    if not available():
        raise RuntimeError("OCR needs tesseract: sudo apt install tesseract-ocr "
                           "(add tesseract-ocr-ron for Romanian diacritics)")


def _words(img: Image.Image, lang: str):
    import pytesseract
    gray = ImageOps.grayscale(img)
    # Light-on-dark UIs (dark themes) OCR much better when inverted.
    if sum(gray.resize((64, 64)).getdata()) / 4096 < 110:
        gray = ImageOps.invert(gray)
    data = pytesseract.image_to_data(gray, lang=lang, output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data["text"]):
        if text.strip() and float(data["conf"][i]) > 30:
            yield dict(text=text, x=data["left"][i], y=data["top"][i], w=data["width"][i], h=data["height"][i],
                       line=(data["block_num"][i], data["par_num"][i], data["line_num"][i]))


def find_text(query: str, lang: str = "eng") -> list[dict]:
    """Every on-screen occurrence of `query` (case-insensitive, may span several words).
    Returns boxes in image coordinates with a click point (cx, cy), best match first."""
    _require()
    v = view()
    full = grab()
    words = list(_words(full, lang))
    q = query.lower().split()
    hits = []
    for i in range(len(words)):
        group = words[i:i + len(q)]
        if len(group) < len(q) or len({w["line"] for w in group}) > 1:
            continue
        joined = " ".join(w["text"].lower() for w in group)
        if " ".join(q) in joined:
            x0 = min(w["x"] for w in group)
            y0 = min(w["y"] for w in group)
            x1 = max(w["x"] + w["w"] for w in group)
            y1 = max(w["y"] + w["h"] for w in group)
            (ix0, iy0), (ix1, iy1) = v.capture_to_image(x0, y0), v.capture_to_image(x1, y1)
            exact = joined == " ".join(q)
            hits.append(dict(text=" ".join(w["text"] for w in group), x=ix0, y=iy0, w=ix1 - ix0, h=iy1 - iy0,
                             cx=(ix0 + ix1) // 2, cy=(iy0 + iy1) // 2, exact=exact))
    hits.sort(key=lambda h: (not h["exact"], h["y"], h["x"]))
    return hits


def read_text(x: int = 0, y: int = 0, w: int = 0, h: int = 0, lang: str = "eng") -> str:
    """OCR the whole screen, or an image-coordinate region. Much cheaper for the AI
    than reading text off a screenshot."""
    _require()
    import pytesseract
    v = view()
    img = grab()
    if w and h:
        s = 1 / v.scale
        img = img.crop((round(x * s), round(y * s), round((x + w) * s), round((y + h) * s)))
    gray = ImageOps.grayscale(img)
    if sum(gray.resize((64, 64)).getdata()) / 4096 < 110:
        gray = ImageOps.invert(gray)
    return pytesseract.image_to_string(gray, lang=lang).strip()
