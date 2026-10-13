"""Top-level package for AutoMonkey."""

__author__ = """Mihail-Cosmin Munteanu"""
__email__ = 'munteanumihailcosmin@gmail.com'
__version__ = '0.4.1'


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


_default_display_env()

from .automonkey import *
