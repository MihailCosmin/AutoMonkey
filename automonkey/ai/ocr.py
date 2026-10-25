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


def _prepare(img: Image.Image) -> tuple[Image.Image, int]:
    """Grayscale, inverted for dark themes, and enlarged 2x when the screen is not huge:
    tesseract is tuned for ~300 dpi print and misses most 9-12 px UI labels (ribbon
    captions, status bars) at their real size. Returns (image, enlargement factor)."""
    gray = ImageOps.grayscale(img)
    # Light-on-dark UIs (dark themes) OCR much better when inverted.
    if sum(gray.resize((64, 64)).getdata()) / 4096 < 110:
        gray = ImageOps.invert(gray)
    factor = 2 if max(gray.size) <= 2600 else 1
    if factor > 1:
        gray = gray.resize((gray.width * factor, gray.height * factor), Image.LANCZOS)
    return gray, factor


def _words(img: Image.Image, lang: str):
    pytesseract = _pytesseract()
    gray, f = _prepare(img)
    data = pytesseract.image_to_data(gray, lang=lang, output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data["text"]):
        if text.strip() and float(data["conf"][i]) > 30:
            yield dict(text=text, x=data["left"][i] // f, y=data["top"][i] // f, w=data["width"][i] // f,
                       h=data["height"][i] // f,
                       line=(data["block_num"][i], data["par_num"][i], data["line_num"][i]))


def _norm(text: str) -> str:
    from .controls import normalize  # pure string helper, no accessibility imports
    return normalize(text)


def _match(words: list[dict], q: list[str]) -> list[dict]:
    """Runs of consecutive words on one line whose text contains the query words."""
    out = []
    for i in range(len(words)):
        group = words[i:i + len(q)]
        if len(group) < len(q) or len({w["line"] for w in group}) > 1:
            continue
        joined = " ".join(_norm(w["text"]) for w in group)
        if " ".join(q) in joined:
            out.append(dict(text=" ".join(w["text"] for w in group), exact=joined == " ".join(q),
                            x0=min(w["x"] for w in group), y0=min(w["y"] for w in group),
                            x1=max(w["x"] + w["w"] for w in group), y1=max(w["y"] + w["h"] for w in group)))
    return out


def _refine(img: Image.Image, words: list[dict], q: list[str], lang: str) -> list[dict]:
    """Second chance for phrases a full-screen pass breaks up (a lone digit or symbol in
    "Count: 2" is often dropped): re-read, enlarged 3x as a single text line, the strip
    that starts at each word matching the first query word."""
    pytesseract = _pytesseract()
    out = []
    for w in words:
        if not (_norm(w["text"]).startswith(q[0]) or q[0].startswith(_norm(w["text"]))):
            continue
        char_w = w["w"] / max(len(w["text"]), 1)
        width = max(w["w"], int(len(" ".join(q)) * char_w * 1.6)) + 4 * w["h"]
        box = (max(0, w["x"] - w["h"]), max(0, w["y"] - w["h"] // 2),
               min(img.width, w["x"] + width), min(img.height, w["y"] + w["h"] * 3 // 2))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        gray, _f = _prepare(img.crop(box))
        gray = gray.resize((gray.width * 3 // 2, gray.height * 3 // 2), Image.LANCZOS)  # 2x * 1.5 = 3x
        text = _norm(pytesseract.image_to_string(gray, lang=lang, config="--psm 7"))
        if " ".join(q) in text:
            est = min(box[2], w["x"] + int(len(" ".join(q)) * char_w * 1.1))
            out.append(dict(text=" ".join(q), exact=False, x0=w["x"], y0=w["y"], x1=est, y1=w["y"] + w["h"]))
    return out


def find_text(query: str, lang: str = "eng", region: tuple[int, int, int, int] | None = None) -> list[dict]:
    """Every occurrence of `query` (case-insensitive, may span several words) on screen,
    or inside `region` = (x, y, w, h) in image coordinates (e.g. the active window: text
    in other windows, such as a terminal showing the test script, can't match then).
    Returns boxes in image coordinates with a click point (cx, cy), best match first."""
    _require()
    v = view()
    img = grab()
    ox = oy = 0
    if region:
        s = 1 / v.scale
        x, y, w, h = region
        box = (max(0, round(x * s)), max(0, round(y * s)),
               min(img.width, round((x + w) * s)), min(img.height, round((y + h) * s)))
        if box[2] > box[0] and box[3] > box[1]:
            img, (ox, oy) = img.crop(box), box[:2]
    q = _norm(query).split()
    if not q:
        return []
    words = list(_words(img, lang))
    found = _match(words, q) or _refine(img, words, q, lang)
    hits = []
    for f in found:
        (ix0, iy0), (ix1, iy1) = v.capture_to_image(ox + f["x0"], oy + f["y0"]), v.capture_to_image(ox + f["x1"], oy + f["y1"])
        hits.append(dict(text=f["text"], x=ix0, y=iy0, w=ix1 - ix0, h=iy1 - iy0,
                         cx=(ix0 + ix1) // 2, cy=(iy0 + iy1) // 2, exact=f["exact"]))
    hits.sort(key=lambda h: (not h["exact"], h["y"], h["x"]))
    return hits


def read_image(img: Image.Image, lang: str = "eng") -> str:
    """OCR a small crop (a label, a button): enlarged 3x, read as a block of text."""
    _require()
    gray, _f = _prepare(img)
    if _f == 1 or max(gray.size) < 400:
        gray = gray.resize((max(1, gray.width * 3 // 2), max(1, gray.height * 3 // 2)), Image.LANCZOS)
    return _pytesseract().image_to_string(gray, lang=lang, config="--psm 6").strip()


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
    gray, _f = _prepare(img)
    return pytesseract.image_to_string(gray, lang=lang).strip()
