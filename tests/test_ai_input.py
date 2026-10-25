"""Unit tests for the AutoMonkey AI input layer (inject, screen.View, script.run, history/replay).

Nothing here touches the real mouse, keyboard or screen: every input/screen function
the code would reach is monkeypatched with a recorder.
"""
import pytest

pytest.importorskip("pyautogui")

from PIL import Image

from automonkey.ai import inject, screen, script
import automonkey.ai as ai


# --- inject.densify ---------------------------------------------------------

def test_densify_straight_line():
    pts = inject.densify([(0, 0), (10, 0)], step=2)
    assert pts[0] == (0, 0)
    assert pts[-1] == (10, 0)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        assert abs(x1 - x0) + abs(y1 - y0) <= 2
    for a, b in zip(pts, pts[1:]):
        assert a != b


def test_densify_keeps_middle_vertex():
    pts = inject.densify([(0, 0), (10, 0), (10, 10)], step=2)
    assert (10, 0) in pts
    assert pts[0] == (0, 0)
    assert pts[-1] == (10, 10)


def test_densify_empty():
    assert inject.densify([]) == []


def test_densify_single_point():
    assert inject.densify([(3.4, 7.6)]) == [(3, 8)]


# --- screen.View ------------------------------------------------------------

def test_view_second_monitor():
    v = screen.View((1920, 1080), max_side=1920, origin=(1920, 0), input_size=(1920, 1080))
    assert v.to_input(0, 0) == (1920, 0)
    assert v.to_input(960, 540) == (2880, 540)
    assert v.to_image(2880, 540) == (960, 540)


def test_view_second_monitor_downscaled():
    v = screen.View((1920, 1080), max_side=960, origin=(1920, 0), input_size=(1920, 1080))
    assert (v.image_w, v.image_h) == (960, 540)
    assert v.to_input(480, 270) == (1920 + 960, 540)


# --- script.run with mocked input -------------------------------------------

@pytest.fixture
def calls(monkeypatch):
    """Mock every input/screen function script.run reaches; return the call recorder."""
    recorded = []

    def recorder(name):
        def rec(*args, **kwargs):
            recorded.append((name, args, kwargs))
        return rec

    monkeypatch.setattr(script.screen, "view",
                        lambda: screen.View((1000, 1000), max_side=1000, origin=(0, 0),
                                            input_size=(1000, 1000)))
    monkeypatch.setattr(script.screen, "wait_stable", lambda *a, **k: (True, 0.0))
    monkeypatch.setattr(script.screen, "grab", lambda: Image.new("RGB", (10, 10)))

    for name in ("click", "drag", "move_to", "scroll", "press", "release", "release_all"):
        monkeypatch.setattr(script.inject, name, recorder("inject." + name))
    for name in ("write", "press", "hotkey"):
        monkeypatch.setattr(script, name, recorder(name))
    monkeypatch.setattr(script.pyautogui, "keyDown", recorder("keyDown"))
    monkeypatch.setattr(script.pyautogui, "keyUp", recorder("keyUp"))
    return recorded


def _named(calls, name):
    return [c for c in calls if c[0] == name]


def test_run_click_variants(calls):
    log, ok = script.run("click 10 20; dclick 1 2; rclick 3 4; mclick 5 6")
    assert ok is True
    clicks = _named(calls, "inject.click")
    assert len(clicks) == 4
    assert clicks[0][1][:2] == (10, 20)
    assert clicks[0][2].get("button", "left") == "left"
    assert clicks[0][2].get("clicks", 1) == 1
    assert clicks[1][2].get("clicks") == 2
    assert clicks[2][2].get("button") == "right"
    assert clicks[3][2].get("button") == "middle"


def test_run_drag(calls):
    log, ok = script.run("drag 1 2 30 40")
    assert ok is True
    drags = _named(calls, "inject.drag")
    assert len(drags) == 1
    assert drags[0][1][0] == [(1, 2), (30, 40)]
    assert drags[0][2].get("button") == "left"

    calls.clear()
    log, ok = script.run("drag 1 2 30 40 right")
    assert ok is True
    drags = _named(calls, "inject.drag")
    assert drags[0][2].get("button") == "right"


def test_run_stroke_and_bad_path(calls):
    log, ok = script.run("stroke 0 0 10 0 10 10")
    assert ok is True
    drags = _named(calls, "inject.drag")
    assert len(drags) == 1
    assert len(drags[0][1][0]) == 3

    calls.clear()
    log, ok = script.run("path 1 2 3")
    assert ok is False
    assert any("FAILED" in line for line in log)


def test_run_scroll(calls):
    log, ok = script.run("scroll -3 50 60")
    assert ok is True
    scrolls = _named(calls, "inject.scroll")
    assert len(scrolls) == 1
    _, args, kwargs = scrolls[0]
    flat = list(args) + list(kwargs.values())
    assert -3 in flat
    assert 50 in flat
    assert 60 in flat
    assert kwargs.get("horizontal") is False

    calls.clear()
    log, ok = script.run("hscroll 2")
    assert ok is True
    scrolls = _named(calls, "inject.scroll")
    assert scrolls[0][2].get("horizontal") is True


def test_run_keydown_keyup(calls):
    log, ok = script.run("keydown ctrl; click 1 1; keyup ctrl")
    assert ok is True
    downs = _named(calls, "keyDown")
    ups = _named(calls, "keyUp")
    assert downs and downs[0][1][0] == "ctrl"
    assert ups and ups[0][1][0] == "ctrl"
    assert calls.index(downs[0]) < calls.index(ups[0])


def test_run_cleanup_releases_keys_and_buttons(calls):
    log, ok = script.run("keydown shift; jump 1 2")
    assert ok is False
    ups = _named(calls, "keyUp")
    assert any(c[1][0] == "shift" for c in ups)
    assert len(_named(calls, "inject.release_all")) == 1

    calls.clear()
    log, ok = script.run("click 1 1")
    assert ok is True
    assert len(_named(calls, "inject.release_all")) == 1


def test_run_unknown_command_stops(calls):
    log, ok = script.run("click 1 1; jump; click 2 2")
    assert ok is False
    assert any("skipped 1 remaining step" in line for line in log)
    assert len(_named(calls, "inject.click")) == 1


def test_run_expect_window(calls, monkeypatch):
    def boom(title):
        raise LookupError("no window")

    monkeypatch.setattr(script.windows, "find_window", boom)
    log, ok = script.run("expect_window Foo")
    assert ok is False

    monkeypatch.setattr(script.windows, "find_window", lambda title: {"title": "Foo bar"})
    log, ok = script.run("expect_window Foo")
    assert ok is True


def test_run_expect_text(calls, monkeypatch):
    def no_window():
        raise LookupError("no active window")

    # No active window: OCR searches the whole screen and there is no tree fallback.
    monkeypatch.setattr(script.windows, "active_window", no_window)
    monkeypatch.setattr(script, "EXPECT_TIMEOUT", 0.0)
    monkeypatch.setattr(script.ocr, "find_text", lambda text, region=None: [])
    log, ok = script.run("expect_text Hello")
    assert ok is False

    hit = {"text": "Hello", "x": 0, "y": 0, "w": 4, "h": 2, "cx": 2, "cy": 1, "exact": True}
    monkeypatch.setattr(script.ocr, "find_text", lambda text, region=None: [hit])
    log, ok = script.run("expect_text Hello")
    assert ok is True

    log, ok = script.run("expect_no_text Hello")
    assert ok is False

    monkeypatch.setattr(script.ocr, "find_text", lambda text, region=None: [])
    log, ok = script.run("expect_no_text Hello")
    assert ok is True


def test_run_expect_change_needs_input(calls):
    log, ok = script.run("expect_change")
    assert ok is False


def test_run_save(calls, tmp_path):
    path = tmp_path / "shots" / "a.png"
    log, ok = script.run(f"save {path}")
    assert ok is True
    assert path.exists()
    assert any("saved" in line for line in log)


# --- ai.history and ai.replay -----------------------------------------------

def test_history(monkeypatch, tmp_path):
    monkeypatch.setattr(ai, "SESSION_DIR", str(tmp_path))
    ai._record("click 1 2; key enter", True, ["1. ok"])
    ai._record("type x", False, ["1. type x -> FAILED: boom"])
    text = ai.history(10)
    assert "click 1 2" in text
    assert "key enter" in text
    assert "type x" in text
    assert "FAILED" in text


def test_replay_passed(monkeypatch, tmp_path):
    monkeypatch.setattr(ai, "SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(ai, "run", lambda script, settle=True: (["1. click 1 1 -> ok"], True))
    path = tmp_path / "t.amk"
    path.write_text("click 1 1", encoding="utf-8")
    ok, log, img = ai.replay(str(path))
    assert ok is True
    assert log.startswith("PASSED")
    assert img is None


def test_replay_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(ai, "SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(ai, "run", lambda script, settle=True: (["1. x -> FAILED"], False))
    monkeypatch.setattr(ai.screen, "grab", lambda: Image.new("RGB", (100, 100)))
    monkeypatch.setattr(ai.screen, "shot", lambda *a, **k: Image.new("RGB", (10, 10)))
    path = tmp_path / "t.amk"
    path.write_text("click 1 1", encoding="utf-8")
    ok, log, img = ai.replay(str(path))
    assert ok is False
    assert log.startswith("FAILED")
    assert (tmp_path / "t.failure.png").exists()
