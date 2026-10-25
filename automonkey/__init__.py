"""Top-level package for AutoMonkey."""

__author__ = """Mihail-Cosmin Munteanu"""
__email__ = 'munteanumihailcosmin@gmail.com'
# Read back from the installed distribution, so [project].version in pyproject.toml stays
# the only place the version is written (see bump_version.py).
try:
    from importlib.metadata import version as _installed_version

    __version__ = _installed_version("AutoMonkey")
except Exception:  # plain source checkout, no installed distribution metadata to read
    __version__ = "0.0.0+unknown"


def _default_display_env():
    """Fill in display/session variables missing when started by a service or an MCP
    client: pyautogui fails to import without DISPLAY, and the AT-SPI backend
    (atspi_funcs.py) can't reach the accessibility bus without DBUS_SESSION_BUS_ADDRESS -
    both are normally set by a login session, which a service/MCP client may not inherit."""
    import os
    import sys
    if not sys.platform.startswith("linux"):
        return
    runtime = os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    if "WAYLAND_DISPLAY" not in os.environ and os.path.exists(os.path.join(runtime, "wayland-0")):
        os.environ["WAYLAND_DISPLAY"] = "wayland-0"
    if "DISPLAY" not in os.environ and os.path.exists("/tmp/.X11-unix/X0"):
        os.environ["DISPLAY"] = ":0"
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
        bus_path = os.path.join(runtime, "bus")
        if os.path.exists(bus_path):
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"


def _dpi_aware():
    """Windows: work in physical pixels on every monitor. Without this, a process is
    "DPI unaware" and on a scaled display (125%, 150%) screenshots, window rectangles and
    mouse coordinates all live in different, virtualised coordinate systems. It must run
    before pyautogui is imported (pyautogui would pick the weaker system-wide awareness)."""
    import sys
    if sys.platform != "win32":
        return
    import ctypes
    try:  # Windows 10 1703+: per-monitor v2
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


_default_display_env()
_dpi_aware()

from .automonkey import *
