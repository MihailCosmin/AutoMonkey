"""Screen capture, coordinate mapping and change detection for AI agents.

Three coordinate spaces exist:
  * capture pixels - what the screenshot backend returns (physical pixels)
  * input pixels   - what pyautogui uses for mouse moves
  * image pixels   - the downscaled screenshot the AI actually looks at

The AI only ever deals with *image pixels*. Everything here converts for it.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import pyautogui
from PIL import Image, ImageDraw, ImageFont

DEFAULT_MAX_SIDE = int(os.environ.get("AUTOMONKEY_AI_MAX_SIDE", "1280"))


def session_type() -> str:
    """'wayland', 'x11', 'win32' or 'darwin'."""
    if sys.platform.startswith("linux"):
        return "wayland" if os.environ.get("WAYLAND_DISPLAY") else "x11"
    return sys.platform


def grab() -> Image.Image:
    """Full-resolution RGB screenshot. Uses grim on Wayland, pyautogui elsewhere."""
    if session_type() == "wayland" and shutil.which("grim"):
        # Capturing full size and resizing in PIL is ~3x faster than `grim -s`.
        out = subprocess.run(["grim", "-t", "ppm", "-"], capture_output=True, check=True).stdout
        return Image.open(io.BytesIO(out)).convert("RGB")
    return pyautogui.screenshot().convert("RGB")


class View:
    """Maps between image pixels (what the AI sees) and input pixels (pyautogui)."""

    def __init__(self, capture_size: tuple[int, int], max_side: int = DEFAULT_MAX_SIDE):
        self.capture_w, self.capture_h = capture_size
        self.input_w, self.input_h = pyautogui.size()
        self.scale = min(1.0, max_side / max(self.capture_w, self.capture_h))
        self.image_w = round(self.capture_w * self.scale)
        self.image_h = round(self.capture_h * self.scale)

    def to_input(self, x: float, y: float) -> tuple[int, int]:
        return (round(x * self.input_w / self.image_w), round(y * self.input_h / self.image_h))

    def to_image(self, x: float, y: float) -> tuple[int, int]:
        return (round(x * self.image_w / self.input_w), round(y * self.image_h / self.input_h))

    def capture_to_image(self, x: float, y: float) -> tuple[int, int]:
        return (round(x * self.scale), round(y * self.scale))

    def describe(self) -> str:
        return f"image {self.image_w}x{self.image_h} (screen {self.input_w}x{self.input_h})"


_view: View | None = None


def view() -> View:
    """The current coordinate mapping (created from a fresh capture if needed)."""
    global _view
    if _view is None:
        _view = View(grab().size)
    return _view


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def draw_grid(img: Image.Image, step: int, origin: tuple[int, int] = (0, 0), unit: float = 1.0) -> Image.Image:
    """Overlay a labelled grid. Labels are in image coordinates of the full view,
    so `origin` and `unit` let zoomed crops show the same numbers as the full shot."""
    img = img.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = _font(11)
    ox, oy = origin
    first_x = (-ox) % step
    for vx in range(ox + first_x, ox + int(img.width / unit) + 1, step):
        px = round((vx - ox) * unit)
        d.line([(px, 0), (px, img.height)], fill=(255, 0, 255, 90), width=1)
        d.text((px + 2, 2), str(vx), fill=(255, 0, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0, 255))
    first_y = (-oy) % step
    for vy in range(oy + first_y, oy + int(img.height / unit) + 1, step):
        py = round((vy - oy) * unit)
        d.line([(0, py), (img.width, py)], fill=(255, 0, 255, 90), width=1)
        d.text((2, py + 2), str(vy), fill=(255, 0, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0, 255))
    return Image.alpha_composite(img, layer).convert("RGB")


def draw_mouse(img: Image.Image, at: tuple[int, int], radius: int = 7) -> Image.Image:
    """Mark the mouse position with a red ring (screenshots don't include the cursor)."""
    d = ImageDraw.Draw(img)
    x, y = at
    d.ellipse([x - radius, y - radius, x + radius, y + radius], outline=(255, 0, 0), width=2)
    return img


def shot(grid: int = 0, max_side: int = DEFAULT_MAX_SIDE, show_mouse: bool = True,
         full: Image.Image | None = None) -> Image.Image:
    """Screenshot scaled for the AI. All coordinates the AI reads off it are valid input."""
    global _view
    full = full or grab()
    _view = View(full.size, max_side)
    img = full.resize((_view.image_w, _view.image_h), Image.LANCZOS) if _view.scale < 1 else full
    if show_mouse:
        img = draw_mouse(img, _view.to_image(*pyautogui.position()))
    if grid:
        img = draw_grid(img, grid)
    return img


def zoom(x: int, y: int, w: int, h: int, grid: int = 0) -> Image.Image:
    """Full-resolution crop of an image-coordinate region, enlarged for reading
    small text. Grid labels (if any) are in the same image coordinates."""
    v = view()
    full = grab()
    s = 1 / v.scale
    box = (round(x * s), round(y * s), round((x + w) * s), round((y + h) * s))
    crop = full.crop(box)
    factor = max(1.0, min(4.0, 800 / max(crop.width, crop.height, 1)))
    crop = crop.resize((round(crop.width * factor), round(crop.height * factor)), Image.LANCZOS)
    if grid:
        crop = draw_grid(crop, grid, origin=(x, y), unit=crop.width / max(w, 1))
    return crop


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False, compress_level=1)
    return buf.getvalue()


# --- change detection -------------------------------------------------------

def _small(img: Image.Image) -> np.ndarray:
    return np.asarray(img.resize((img.width // 8, img.height // 8), Image.NEAREST).convert("L"), dtype=np.int16)


def changed_fraction(a: np.ndarray, b: np.ndarray, threshold: int = 24) -> float:
    if a.shape != b.shape:
        return 1.0
    return float((np.abs(a - b) > threshold).mean())


# A blinking text caret or a spinner changes ~0.05% of the screen; ignore that.
NOISE = 0.002


def wait_stable(stable_for: float = 1.0, timeout: float = 15.0, poll: float = 0.15) -> tuple[bool, float]:
    """Wait until the screen stops changing. Returns (stable?, seconds waited)."""
    start = time.monotonic()
    last = _small(grab())
    same_since = time.monotonic()
    while time.monotonic() - start < timeout:
        time.sleep(poll)
        cur = _small(grab())
        if changed_fraction(last, cur) > NOISE:
            last, same_since = cur, time.monotonic()
        elif time.monotonic() - same_since >= stable_for:
            return True, time.monotonic() - start
    return False, time.monotonic() - start


def wait_change(baseline: Image.Image | None = None, timeout: float = 15.0, poll: float = 0.15) -> tuple[bool, float]:
    """Wait until the screen differs from `baseline` (default: now)."""
    start = time.monotonic()
    base = _small(baseline or grab())
    while time.monotonic() - start < timeout:
        time.sleep(poll)
        if changed_fraction(base, _small(grab())) > NOISE:
            return True, time.monotonic() - start
    return False, time.monotonic() - start


def diff_summary(before: Image.Image, after: Image.Image) -> str:
    """Human/AI readable description of what changed, in image coordinates."""
    a, b = _small(before), _small(after)
    if a.shape != b.shape:
        return "screen size changed"
    mask = np.abs(a - b) > 24
    frac = float(mask.mean())
    if frac <= NOISE:
        return "screen did NOT change"
    ys, xs = np.nonzero(mask)
    v = view()
    x0, y0 = v.capture_to_image(xs.min() * 8, ys.min() * 8)
    x1, y1 = v.capture_to_image((xs.max() + 1) * 8, (ys.max() + 1) * 8)
    return f"screen changed: {frac:.0%} of pixels, region x={x0}..{x1} y={y0}..{y1}"
