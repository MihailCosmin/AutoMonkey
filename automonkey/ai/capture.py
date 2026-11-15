"""Documentation capture: one window or region to a PNG at native resolution, the bounds
of named controls as JSON (for callouts), and a video of one window.

Built for the user-manual screenshots of the force apps (force-libs docs/user-manuals.md):
the AI layer's own screenshots are downscaled for the model, these are not.

    capture_window("Notepad")            -> PNG of that window, physical pixels, no shadow
    capture_region(100, 100, 640, 480)   -> PNG of a screen rectangle (physical pixels)
    control_bounds("Notepad", only=["File", "Save"])   -> dict, write it with json.dump
    start_recording("out.mp4", window="Notepad") ... stop_recording()

Coordinates in the bounds JSON are physical pixels relative to the top-left corner of the
captured picture (`pad` included), so they can be drawn on the PNG without scaling.
Windows (UI Automation, gdigrab) and Linux X11/Xvfb (AT-SPI, x11grab); Wayland is not
supported for recording.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import pyautogui
from PIL import Image

from . import controls, screen, windows


class CaptureError(Exception):
    pass


# --- pictures -----------------------------------------------------------------

def grab_rect(x: int, y: int, w: int, h: int) -> Image.Image:
    """Native-resolution RGB picture of a screen rectangle (physical pixels, any monitor)."""
    if w <= 0 or h <= 0:
        raise CaptureError(f"empty rectangle {w}x{h}")
    if screen.session_type() == "wayland":
        if not shutil.which("grim"):
            raise CaptureError("Wayland capture needs grim")
        out = subprocess.run(["grim", "-g", f"{x},{y} {w}x{h}", "-t", "ppm", "-"],
                             capture_output=True, check=True).stdout
        return Image.open(io.BytesIO(out)).convert("RGB")
    if sys.platform == "win32":
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).convert("RGB")
    return pyautogui.screenshot(region=(x, y, w, h)).convert("RGB")


def _virtual_screen() -> tuple[int, int, int, int]:
    mons = screen.monitors()
    x0 = min(m[0] for m in mons)
    y0 = min(m[1] for m in mons)
    x1 = max(m[0] + m[2] for m in mons)
    y1 = max(m[1] + m[3] for m in mons)
    return x0, y0, x1 - x0, y1 - y0


def _check_on_screen(x: int, y: int, w: int, h: int, what: str):
    vx, vy, vw, vh = _virtual_screen()
    if x < vx or y < vy or x + w > vx + vw or y + h > vy + vh:
        raise CaptureError(f"{what} ({w}x{h} at {x},{y}) is not completely on the screen "
                           f"({vw}x{vh} at {vx},{vy}): move or resize it first")


def window_box(window: str | int | None = None, pad: int = 0, focus: bool = True) -> tuple[dict, tuple[int, int, int, int]]:
    """(window, (x, y, w, h)) of a window in physical screen pixels, grown by `pad`. With
    `focus` the window is raised first and the screen is let settle, so nothing covers it."""
    w = windows.find_window(window) if window is not None else windows.active_window()
    if focus:
        w = windows.focus(w["id"])
        screen.wait_stable(stable_for=0.4, timeout=5)
        w = windows.find_window(w["id"])
    if w.get("minimized"):
        raise CaptureError(f"window {w['title']!r} is minimized")
    box = (w["x"] - pad, w["y"] - pad, w["w"] + 2 * pad, w["h"] + 2 * pad)
    return w, box


def capture_window(window: str | int | None = None, pad: int = 0, focus: bool = True) -> Image.Image:
    """Picture of ONE window at native resolution (the visible frame, without the invisible
    resize borders or the drop shadow of Windows 11). `window` is a title / class / id; the
    active window when None."""
    _w, box = window_box(window, pad, focus)
    _check_on_screen(*box, what="the window")
    return grab_rect(*box)


def capture_region(x: int, y: int, w: int, h: int) -> Image.Image:
    """Picture of a screen rectangle (physical pixels) at native resolution."""
    _check_on_screen(x, y, w, h, what="the region")
    return grab_rect(x, y, w, h)


def save_png(img: Image.Image, path: str) -> str:
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, format="PNG")
    return path


# --- control bounds -------------------------------------------------------------

def control_bounds(window: str | int | None = None, only: list[str] | None = None, pad: int = 0,
                   named_only: bool = True, focus: bool = True) -> dict:
    """The boxes of a window's controls, relative to the picture `capture_window(window, pad)`
    makes, ready for json.dump:

        {"window": {...}, "size": {"w", "h"},
         "controls": [{"name", "type", "id", "enabled", "x", "y", "w", "h"}, ...]}

    `only` lists the names (as in `click_control`, also "Type:Name" and automation ids) of
    the controls wanted, in that order, each reported once (the best match); a name that is
    not found raises LookupError. Without it every control that has a box is listed (only
    named ones unless `named_only` is False). Controls with no box (hidden, scrolled away)
    are left out."""
    w, (bx, by, bw, bh) = window_box(window, pad, focus)
    items = [p for _level, _ei, p in controls.walk(w["id"]) if p.get("screen_rect")]
    if only:
        chosen = [dict(controls.pick(items, name, window=w["title"]), query=name) for name in only]
    else:
        chosen = [p for p in items if p["name"] or p["auto_id"] or not named_only]
    out = []
    for p in chosen:
        sx, sy, sw, sh = p["screen_rect"]
        entry = dict(name=p["name"], type=p["type"], id=p["auto_id"], enabled=p["enabled"],
                     x=sx - bx, y=sy - by, w=sw, h=sh)
        if "query" in p:
            entry["query"] = p["query"]
        out.append(entry)
    return {"window": {"title": w["title"], "class": w["wm_class"], "pid": w["pid"], "id": w["id"],
                       "x": w["x"], "y": w["y"], "w": w["w"], "h": w["h"]},
            "size": {"w": bw, "h": bh}, "pad": pad, "controls": out}


# --- video -------------------------------------------------------------------------

def ffmpeg_path() -> str:
    path = os.environ.get("AUTOMONKEY_FFMPEG") or shutil.which("ffmpeg")
    if not path:
        raise CaptureError("ffmpeg not found (winget install Gyan.FFmpeg / sudo apt install ffmpeg), "
                           "or set AUTOMONKEY_FFMPEG to its path")
    return path


def _even(n: int) -> int:
    return max(2, n - n % 2)  # H.264 and VP9 in yuv420p need even sizes


def ffmpeg_command(path: str, box: tuple[int, int, int, int], fps: int = 15, mouse: bool = True,
                   ffmpeg: str = "ffmpeg", platform: str | None = None, display: str | None = None) -> list[str]:
    """The ffmpeg command line that records the screen rectangle `box` to `path` (.mp4 =
    H.264, .webm = VP9, .gif). gdigrab on Windows, x11grab on Linux."""
    platform = platform or sys.platform
    x, y, w, h = box
    w, h = _even(w), _even(h)
    if platform == "win32":
        src = ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1" if mouse else "0",
               "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop"]
    else:
        display = display or os.environ.get("DISPLAY") or ":0"
        src = ["-f", "x11grab", "-framerate", str(fps), "-draw_mouse", "1" if mouse else "0",
               "-video_size", f"{w}x{h}", "-i", f"{display}+{x},{y}"]
    ext = os.path.splitext(path)[1].lower()
    if ext == ".webm":
        enc = ["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "0", "-crf", "32",
               "-pix_fmt", "yuv420p"]
    elif ext == ".gif":
        enc = ["-vf", "split[a][b];[a]palettegen[p];[b][p]paletteuse"]
    elif ext in (".mp4", ".mkv", ".mov"):
        enc = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"]
        if ext != ".mkv":
            enc += ["-movflags", "+faststart"]
    else:
        raise CaptureError(f"unsupported video type {ext!r} (use .mp4, .webm, .gif or .mkv)")
    return [ffmpeg, "-y", "-hide_banner", "-loglevel", "warning", *src, *enc, path]


class _Recording:
    def __init__(self, proc, path, log_path, started, box):
        self.proc, self.path, self.log_path, self.started, self.box = proc, path, log_path, started, box


_recording: _Recording | None = None


def recording() -> bool:
    return _recording is not None and _recording.proc.poll() is None


def start_recording(path: str, window: str | int | None = None, region: tuple[int, int, int, int] | None = None,
                    fps: int = 15, pad: int = 0, mouse: bool = True) -> str:
    """Record a window (its position when this is called) or a screen region to `path`
    until stop_recording(). Returns a description. One recording at a time."""
    global _recording
    if recording():
        raise CaptureError(f"already recording to {_recording.path}; call stop_recording first")
    if screen.session_type() == "wayland":
        raise CaptureError("recording needs X11 (x11grab) or Windows (gdigrab); Wayland is not supported")
    ffmpeg = ffmpeg_path()
    if region:
        box, what = tuple(region), "region"
    else:
        w, box = window_box(window, pad)
        what = f"window {w['title']!r}"
    _check_on_screen(*box, what=what)
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cmd = ffmpeg_command(path, box, fps, mouse, ffmpeg)
    log_fd, log_path = tempfile.mkstemp(prefix="automonkey_ffmpeg_", suffix=".log")
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_fd, **kw)
    os.close(log_fd)
    time.sleep(0.8)
    if proc.poll() is not None:
        err = _read_log(log_path)
        raise CaptureError(f"ffmpeg stopped at start (exit {proc.returncode}): {err}")
    _recording = _Recording(proc, path, log_path, time.monotonic(), box)
    return f"recording {what} {box[2]}x{box[3]} at {fps} fps to {path}"


def _read_log(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        os.remove(path)
        return text[-600:]
    except OSError:
        return ""


def stop_recording(timeout: float = 20.0) -> str:
    """Finish the video (ffmpeg gets `q`, so the file is complete and playable)."""
    global _recording
    rec, _recording = _recording, None
    if rec is None:
        raise CaptureError("no recording is running")
    seconds = time.monotonic() - rec.started
    if rec.proc.poll() is None:
        try:
            rec.proc.stdin.write(b"q\n")
            rec.proc.stdin.flush()
            rec.proc.stdin.close()
        except OSError:
            pass
        try:
            rec.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            rec.proc.kill()
            rec.proc.wait()
            raise CaptureError(f"ffmpeg did not finish within {timeout:.0f}s and was killed; {rec.path} may be broken")
    err = _read_log(rec.log_path)
    if rec.proc.returncode not in (0, None) and not os.path.exists(rec.path):
        raise CaptureError(f"ffmpeg failed (exit {rec.proc.returncode}): {err}")
    if not os.path.exists(rec.path) or os.path.getsize(rec.path) == 0:
        raise CaptureError(f"no video was written to {rec.path}: {err}")
    return f"saved {rec.path} ({seconds:.1f}s, {os.path.getsize(rec.path) // 1024} KB)"


# --- window size -------------------------------------------------------------------

def resize_window(window: str | int | None, w: int, h: int) -> dict:
    """Make the visible frame of a window exactly w x h physical pixels (the size
    `capture_window` returns), keeping its top-left corner. Leaves maximized state."""
    win = windows.find_window(window) if window is not None else windows.active_window()
    windows.set_size(win["id"], w, h)
    time.sleep(0.4)
    return windows.find_window(win["id"])


_SPLIT_PATH = re.compile(r'\s*(?:"(?P<q>[^"]+)"|(?P<p>\S+))\s*(?P<rest>.*)$', re.S)


def split_path(rest: str) -> tuple[str, str]:
    """('"my dir/a.png" in Notepad') -> ('my dir/a.png', 'in Notepad'): a path, quoted when it has spaces."""
    m = _SPLIT_PATH.match(rest)
    if not m or not (m.group("q") or m.group("p")):
        raise CaptureError("a file path is needed")
    return m.group("q") or m.group("p"), m.group("rest").strip()
