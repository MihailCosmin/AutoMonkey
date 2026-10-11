"""Unit tests for automonkey.ai helpers that don't touch the real screen."""
import pytest

pytest.importorskip("pyautogui")

from automonkey.ai import screen
from automonkey.ai.script import split_script, run_step, StepError


def test_split_script_semicolons_newlines_comments():
    assert split_script("click 1 2; type a\;b\n# note\n key enter ") == ["click 1 2", "type a;b", "key enter"]


def test_view_round_trip(monkeypatch):
    monkeypatch.setattr(screen.pyautogui, "size", lambda: (1920, 1200))
    v = screen.View((1920, 1200), max_side=960)
    assert (v.image_w, v.image_h) == (960, 600)
    assert v.to_input(480, 300) == (960, 600)
    assert v.to_image(1920, 1200) == (960, 600)


def test_view_hidpi_capture(monkeypatch):
    # Capture in physical pixels (2x) but input in logical pixels
    monkeypatch.setattr(screen.pyautogui, "size", lambda: (1280, 800))
    v = screen.View((2560, 1600), max_side=1280)
    assert v.to_input(1280, 800) == (1280, 800)


def test_unknown_command():
    with pytest.raises(StepError):
        run_step("jump 1 2")
