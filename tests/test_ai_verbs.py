"""Unit tests for the newer AutoMonkey AI verbs: controls.normalize, `finally:` blocks,
failure_image, expect_* retries, _text_scope, drag_control, expect_order, the launch
reuse guard and ai.replay's failure screenshot.

Nothing here touches the real mouse, keyboard or screen: every input/screen function
the code would reach is monkeypatched with a recorder.
"""
import pytest

pytest.importorskip("pyautogui")

from PIL import Image

from automonkey.ai import script, screen, controls
import automonkey.ai as ai


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    """Mock every input/screen function script.run reaches; return the call recorder."""
    calls = []

    def recorder(name):
        def rec(*args, **kwargs):
            calls.append((name, args, kwargs))
        return rec

    monkeypatch.setattr(script, "EXPECT_TIMEOUT", 0.2)
    monkeypatch.setattr(script.screen, "view",
                        lambda: screen.View((1000, 1000), max_side=1000, origin=(0, 0),
                                            input_size=(1000, 1000)))
    monkeypatch.setattr(script.screen, "wait_stable", lambda *a, **k: (True, 0.0))
    monkeypatch.setattr(script.screen, "grab", lambda: Image.new("RGB", (10, 10)))
    monkeypatch.setattr(script.time, "sleep", lambda *a, **k: None)

    for name in ("click", "drag", "release_all"):
        monkeypatch.setattr(script.inject, name, recorder("inject." + name))
    return calls


def _named(calls, name):
    return [c for c in calls if c[0] == name]


# --- controls.normalize -----------------------------------------------------

def test_normalize_typographic_and_mnemonic():
    assert controls.normalize("Don\u2019t  Save\u2026") == "don't save..."
    assert controls.normalize("&File") == "file"


def test_normalize_accents():
    assert controls.normalize("Zo\u00eb Caf\u00e9") == "zoe cafe"


def test_normalize_spaces():
    assert controls.normalize("a\u00a0b") == "a b"
    assert controls.normalize("a \u00a0  b") == "a b"


# --- finally blocks ---------------------------------------------------------

def test_finally_runs_after_failure(fake_env):
    log, ok = script.run("click 1 1; jump; click 2 2\nfinally:\nclick 9 9")
    assert ok is False
    clicks = [c[1][:2] for c in _named(fake_env, "inject.click")]
    assert clicks == [(1, 1), (9, 9)]
    assert any(line.startswith("finally:") for line in log)


def test_finally_failure_is_ignored(fake_env):
    log, ok = script.run("click 1 1\nfinally:\njump")
    assert ok is True
    assert any("ignored in finally" in line for line in log)


# --- failure_image ----------------------------------------------------------

def test_failure_image_set_on_failure(fake_env):
    log, ok = script.run("jump")
    assert ok is False
    assert script.failure_image is not None


def test_failure_image_none_on_success(fake_env):
    log, ok = script.run("click 1 1")
    assert ok is True
    assert script.failure_image is None


# --- expect retry -----------------------------------------------------------

def test_expect_window_retries_until_found(fake_env, monkeypatch):
    attempts = []

    def find_window(title):
        attempts.append(title)
        if len(attempts) < 3:
            raise LookupError("not yet")
        return {"title": "Late"}

    monkeypatch.setattr(script.windows, "find_window", find_window)
    log, ok = script.run("expect_window Late")
    assert ok is True
    assert len(attempts) == 3


def test_expect_window_always_missing(fake_env, monkeypatch):
    def find_window(title):
        raise LookupError("no window")

    monkeypatch.setattr(script.windows, "find_window", find_window)
    log, ok = script.run("expect_window Late")
    assert ok is False


# --- _text_scope ------------------------------------------------------------

def test_text_scope_active_window(fake_env, monkeypatch):
    monkeypatch.setattr(script.windows, "active_window",
                        lambda: {"id": 1, "title": "App", "x": 100, "y": 200, "w": 300, "h": 400})
    assert script._text_scope("Saved") == ("Saved", (100, 200, 300, 400), "in 'App'")


def test_text_scope_screen_prefix(fake_env, monkeypatch):
    monkeypatch.setattr(script.windows, "active_window",
                        lambda: {"id": 1, "title": "App", "x": 100, "y": 200, "w": 300, "h": 400})
    assert script._text_scope("screen: Saved") == ("Saved", None, "on screen")


def test_text_scope_no_active_window(fake_env, monkeypatch):
    def boom():
        raise LookupError("no active window")

    monkeypatch.setattr(script.windows, "active_window", boom)
    text, region, where = script._text_scope("Saved")
    assert text == "Saved"
    assert region is None


# --- drag_control and expect_order ------------------------------------------

def _control(name, rect):
    return {"type": "ListItem", "name": name, "auto_id": "", "enabled": True, "rect": rect}


@pytest.fixture
def fake_controls(monkeypatch):
    table = {
        "Alpha": _control("Alpha", (10, 10, 20, 20)),
        "Beta": _control("Beta", (10, 50, 20, 20)),
        "Delta": _control("Delta", (10, 100, 20, 20)),
    }

    def find(window, name, control_type=None):
        if name not in table:
            raise LookupError(f"no control named {name!r}")
        return table[name]

    monkeypatch.setattr(controls, "find", find)
    monkeypatch.setattr(script.windows, "active_window",
                        lambda: {"id": 5, "title": "W", "x": 0, "y": 0, "w": 10, "h": 10})
    return table


def test_drag_control(fake_env, fake_controls):
    log, ok = script.run("drag_control Alpha to Delta")
    assert ok is True
    drags = _named(fake_env, "inject.drag")
    assert len(drags) == 1
    assert drags[0][1][0] == [(20, 20), (20, 110)]


def test_drag_control_needs_target(fake_env, fake_controls):
    log, ok = script.run("drag_control Alpha")
    assert ok is False


def test_expect_order_ok(fake_env, fake_controls):
    log, ok = script.run("expect_order Alpha, Beta, Delta")
    assert ok is True


def test_expect_order_wrong(fake_env, fake_controls):
    log, ok = script.run("expect_order Delta, Alpha")
    assert ok is False
    assert any("expected" in line for line in log)


# --- launch reuse guard -----------------------------------------------------

def test_launch_reused_stops(fake_env, monkeypatch):
    monkeypatch.setattr(script.windows, "launch",
                        lambda command: {"id": 7, "title": "Notes", "reused": True})
    monkeypatch.setattr(script.windows, "focus", lambda window: {"id": 7, "title": "Notes"})
    log, ok = script.run("launch notes; click 1 1")
    assert ok is False
    assert any("reused" in line for line in log)
    assert _named(fake_env, "inject.click") == []


def test_launch_fresh_continues(fake_env, monkeypatch):
    monkeypatch.setattr(script.windows, "launch",
                        lambda command: {"id": 7, "title": "Notes", "reused": False})
    monkeypatch.setattr(script.windows, "focus", lambda window: {"id": 7, "title": "Notes"})
    log, ok = script.run("launch notes; click 1 1")
    assert ok is True
    assert len(_named(fake_env, "inject.click")) == 1


# --- ai.replay uses script.failure_image ------------------------------------

def test_replay_writes_failure_screenshot(fake_env, monkeypatch, tmp_path):
    monkeypatch.setattr(ai.screen, "shot", lambda full=None, **k: Image.new("RGB", (5, 5)))
    path = tmp_path / "b.amk"
    path.write_text("jump", encoding="utf-8")
    ok, log, img = ai.replay(str(path))
    assert ok is False
    assert (tmp_path / "b.failure.png").exists()
