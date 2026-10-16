"""Integration tests for automonkey.atspi_funcs against a real AT-SPI bus and real apps.

Opt-in (needs a real desktop, GUI apps, and a few seconds per test): set
AUTOMONKEY_ATSPI_INTEGRATION=1. Each test additionally skips if its target app isn't
installed, and the whole file skips if this interpreter can't import the AT-SPI bindings
(python3-gi is built for the distro's own python3, not for every interpreter), so this
file is always safe to collect/run anywhere.

CI: see .github/workflows/python-package.yml - installs python3-gi, gir1.2-atspi-2.0,
at-spi2-core, xvfb, gnome-calculator, gnome-text-editor and runs under
xvfb-run + dbus-run-session.
"""
import os
import shutil
import sys
import time

import pytest

import automonkey.atspi_funcs as af


def _atspi_bindings_available():
    """True when this interpreter can import the AT-SPI bindings.

    The file's guarantee is that it is always safe to collect and run, and that has to
    mean skipping - not failing - where the bindings are unusable. CI is exactly that
    case: it runs under whichever interpreter actions/setup-python put on PATH, while
    python3-gi installs PyGObject for Ubuntu's own system python3, so `import gi`
    half-works (gi/__init__.py loads, then `from . import _gi` fails against an extension
    built for a different ABI) - a mismatch that leaves the module importable but useless.
    See pywinauto_for_linux.md section 6.
    """
    try:
        import gi  # pylint: disable=import-outside-toplevel

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi  # noqa: F401  # pylint: disable=import-outside-toplevel
    except (ImportError, ValueError):
        return False
    return True


pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="atspi_funcs is Linux-only"),
    pytest.mark.skipif(
        os.environ.get("AUTOMONKEY_ATSPI_INTEGRATION") != "1",
        reason="opt-in: set AUTOMONKEY_ATSPI_INTEGRATION=1 to run against a real desktop",
    ),
    pytest.mark.skipif(
        not _atspi_bindings_available(),
        reason="the AT-SPI bindings (python3-gi) are not importable by this interpreter",
    ),
]


def _stop(app):
    """SIGTERM, then SIGKILL if it's still around - a plain SIGTERM alone was
    occasionally not enough to make gnome-calculator actually exit in time, found while
    running these tests for real."""
    import subprocess
    try:
        pid = str(app.get_process_id())
    except Exception:  # pylint: disable=broad-except
        return
    subprocess.run(["kill", pid], check=False)
    time.sleep(0.5)
    subprocess.run(["kill", "-9", pid], check=False)


@pytest.mark.skipif(shutil.which("gnome-calculator") is None, reason="gnome-calculator not installed")
def test_gnome_calculator_digit_buttons_and_display():
    # A short sleep between clicks is needed: Atspi.Action.do_action() returns once the
    # D-Bus call completes, not once the app has processed the resulting GTK signal -
    # confirmed directly (rapid-fire clicks with no delay dropped "3" entirely, reading
    # back "5+" instead of "5+3"; adding ~0.3s between clicks fixed it every time).
    app = af.start_app("gnome-calculator", timeout=15)
    try:
        for label in ("5", "+", "3"):
            af.click_control("Calculator", {"title": label, "control_type": "Button"}, invoke=True)
            time.sleep(0.3)
        display = af.get_control_text("Calculator", {"control_type": "Edit"})
        assert "5" in display and "3" in display
    finally:
        _stop(app)


@pytest.mark.skipif(shutil.which("gnome-text-editor") is None, reason="gnome-text-editor not installed")
def test_gnome_text_editor_type_and_read_back():
    # control_type is "Edit" (AT-SPI role "text"), not "Document": confirmed against
    # mousepad (also GtkSourceView-based) during manual validation of this test's
    # pattern - plain GTK text editors expose their main text area as a Text
    # interface/role, not Document* (that's for LibreOffice/WebKit-style content).
    app = af.start_app("gnome-text-editor", timeout=15)
    try:
        af.type_in_control(
            "Text Editor", {"control_type": "Edit"}, text="hello from the AT-SPI integration test"
        )
        text = af.get_control_text("Text Editor", {"control_type": "Edit"})
        assert "hello from the AT-SPI integration test" in text
    finally:
        _stop(app)
