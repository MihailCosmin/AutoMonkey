"""Optional OCR: find text on screen so the AI can click by label instead of coordinates.

Needs the tesseract binary. Installation differs per OS:
  Linux   `sudo apt install tesseract-ocr` (add tesseract-ocr-ron for Romanian diacritics)
  macOS   `brew install tesseract`
  Windows `winget install UB-Mannheim.TesseractOCR`

The binary is located via $TESSERACT_CMD, then PATH, then (Windows) the PATH saved
in the registry, then the usual install directories -- so OCR works even when the
PATH of the process that launched us predates the tesseract install (e.g. an
already-running MCP server, or a macOS GUI app that never sees Homebrew's PATH).
"""
from __future__ import annotations

import os
import shutil
import sys

from PIL import Image, ImageOps

from .screen import grab, view

def _candidates() -> list[str]:
    if sys.platform == "win32":
        env = os.environ.get
        dirs = [env("ProgramFiles", r"C:\Program Files"), env("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                os.path.join(env("LOCALAPPDATA", ""), "Programs")]  # per-user installs
        return ([os.path.join(d, "Tesseract-OCR", "tesseract.exe") for d in dirs]
                + [os.path.join(env("USERPROFILE", ""), "scoop", "shims", "tesseract.exe"),
                   os.path.join(env("ChocolateyInstall", r"C:\ProgramData\chocolatey"), "bin", "tesseract.exe")])
    return ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/opt/local/bin/tesseract",
            "/usr/bin/tesseract", "/snap/bin/tesseract"]


def _registry_path() -> str:
    """PATH as currently saved in the registry: installers update it there, but a running
    process keeps the PATH it started with."""
    import winreg
    parts = []
    for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(hive, key) as k:
                parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        except OSError:
            pass
    return os.pathsep.join(parts)


_found: str | None = None


def tesseract_cmd() -> str | None:
    """Locate the tesseract binary, or None if it isn't installed. $TESSERACT_CMD, when
    set, is used exactly (a path or a command name); a wrong value is not silently
    replaced by another tesseract."""
    global _found
    env = os.environ.get("TESSERACT_CMD")
    if env:
        return shutil.which(env)  # also accepts a full path, and adds .exe on Windows
    if _found and os.path.isfile(_found):
        return _found
    _found = shutil.which("tesseract")
    if not _found and sys.platform == "win32":
        _found = shutil.which("tesseract", path=_registry_path())
    if not _found:
        _found = next((c for c in _candidates() if os.path.isfile(c)), None)
    return _found


def available() -> bool:
    return tesseract_cmd() is not None


def _require():
    if available():
        return
    env = os.environ.get("TESSERACT_CMD")
    if env:
        raise RuntimeError(f"OCR: TESSERACT_CMD={env!r} is not an executable tesseract")
    if sys.platform == "win32":
        hint = "winget install UB-Mannheim.TesseractOCR (or set TESSERACT_CMD)"
    elif sys.platform == "darwin":
        hint = "brew install tesseract"
    else:
        hint = "sudo apt install tesseract-ocr (add tesseract-ocr-ron for Romanian diacritics)"
    raise RuntimeError(f"OCR needs tesseract: {hint}")


def _pytesseract():
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd()
    return pytesseract


def _words(img: Image.Image, lang: str):
    pytesseract = _pytesseract()
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
    pytesseract = _pytesseract()
    v = view()
    img = grab()
    if w and h:
        s = 1 / v.scale
        img = img.crop((round(x * s), round(y * s), round((x + w) * s), round((y + h) * s)))
    gray = ImageOps.grayscale(img)
    if sum(gray.resize((64, 64)).getdata()) / 4096 < 110:
        gray = ImageOps.invert(gray)
    return pytesseract.image_to_string(gray, lang=lang).strip()
