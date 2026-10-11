"""Top-level package for AutoMonkey."""

__author__ = """Mihail-Cosmin Munteanu"""
__email__ = 'munteanumihailcosmin@gmail.com'
__version__ = '0.2.7'


def _default_display_env():
    """Fill in display variables missing when started by a service or an MCP client
    (pyautogui fails to import without DISPLAY)."""
    import os
    import sys
    if not sys.platform.startswith("linux"):
        return
    runtime = os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    if "WAYLAND_DISPLAY" not in os.environ and os.path.exists(os.path.join(runtime, "wayland-0")):
        os.environ["WAYLAND_DISPLAY"] = "wayland-0"
    if "DISPLAY" not in os.environ and os.path.exists("/tmp/.X11-unix/X0"):
        os.environ["DISPLAY"] = ":0"


_default_display_env()

from .automonkey import *
