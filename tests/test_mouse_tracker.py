"""Regression tests for GitHub issue #3 ("PositionTracker not working").

The issue had two halves: merely constructing a PositionTracker opened a Tk
window it shouldn't, and destroy_() blew up on an instance that was never
started. The coordinate rendering was the part that already worked, and is
covered by test_start_shows_the_cursor_coordinates.
"""
import pytest

tkinter = pytest.importorskip("tkinter")

from automonkey import PositionTracker  # noqa: E402


def test_constructing_a_tracker_opens_no_window():
    # Documented usage is `tracker = PositionTracker(); tracker.start()`, so nothing
    # may appear on screen before start() runs.
    root_before = tkinter._default_root
    tracker = PositionTracker()
    assert tracker.window is None
    assert tkinter._default_root is root_before, "constructing created a Tk root"


def test_destroy_is_safe_on_a_tracker_that_was_never_started():
    tracker = PositionTracker()
    tracker.destroy_()  # used to raise ValueError from after_cancel(None)
    assert tracker.window is None


def test_start_shows_the_cursor_coordinates():
    tracker = PositionTracker(follow_mouse=False)
    captured = {}
    real_tk = tkinter.Tk

    def tk_factory(*args, **kwargs):
        """Hand back a real Tk root, primed to snapshot the canvas and close."""
        root = real_tk(*args, **kwargs)

        def grab_and_close():
            canvas = tracker.window.canvas
            captured["texts"] = [
                canvas.itemcget(item, "text")
                for item in canvas.find_all()
                if canvas.type(item) == "text"
            ]
            tracker.destroy_()

        root.after(500, grab_and_close)
        return root

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("automonkey.mouse_tracker.Tk", tk_factory)
    try:
        tracker.start()
    except tkinter.TclError as exc:  # no display available (headless CI without xvfb)
        pytest.skip(f"no usable display: {exc}")
    finally:
        monkeypatch.undo()

    texts = captured.get("texts", [])
    assert any(t.startswith("x=") and ", y=" in t for t in texts), \
        f"cursor coordinates were not drawn on the overlay, got {texts!r}"