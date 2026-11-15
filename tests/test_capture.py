"""Unit tests for the documentation capture tools (automonkey/ai/capture.py and the shot, bounds,
record steps of the script language). No real screen, window or ffmpeg is used."""
import argparse
import json
import os

import pytest

pytest.importorskip("pyautogui")

from PIL import Image

from automonkey.ai import __main__ as cli
from automonkey.ai import capture, controls, fill_vars, script
from automonkey.ai.script import StepError, run_step, split_script

WINDOW = dict(id=77, title="My App", wm_class="app.exe", pid=5, x=100, y=50, w=640, h=480, active=True)


def _props(name, rect, type_="Button", auto_id="", enabled=True):
    return dict(type=type_, name=name, auto_id=auto_id, enabled=enabled, rect=rect, screen_rect=rect)


@pytest.fixture
def fake_window(monkeypatch):
    monkeypatch.setattr(capture, "window_box", lambda window=None, pad=0, focus=True:
                        (WINDOW, (WINDOW["x"] - pad, WINDOW["y"] - pad, WINDOW["w"] + 2 * pad, WINDOW["h"] + 2 * pad)))
    items = [
        _props("File", (110, 60, 40, 20), "MenuItem"),
        _props("Save", (300, 500, 80, 30)),
        _props("", (120, 100, 10, 10), "Pane"),            # nameless: skipped by default
        _props("Hidden", None),                              # no box: never listed
        _props("Name", (130, 120, 200, 24), "Edit", auto_id="main.nameEdit"),
    ]
    items[3]["screen_rect"] = None
    monkeypatch.setattr(controls, "walk", lambda window, *a, **k: iter((0, None, p) for p in items))


def test_bounds_are_relative_to_the_window_picture(fake_window):
    data = capture.control_bounds("My App")
    assert data["window"]["title"] == "My App"
    assert data["size"] == {"w": 640, "h": 480}
    names = [c["name"] for c in data["controls"]]
    assert names == ["File", "Save", "Name"]              # nameless and boxless controls left out
    file_ = data["controls"][0]
    assert (file_["x"], file_["y"], file_["w"], file_["h"]) == (10, 10, 40, 20)
    assert data["controls"][2]["id"] == "main.nameEdit"


def test_bounds_with_pad_shift_and_grow_the_picture(fake_window):
    data = capture.control_bounds("My App", pad=8)
    assert data["size"] == {"w": 656, "h": 496}
    assert (data["controls"][0]["x"], data["controls"][0]["y"]) == (18, 18)


def test_bounds_only_keeps_the_order_and_reports_a_missing_name(fake_window):
    data = capture.control_bounds("My App", only=["Save", "nameEdit"])
    assert [c["query"] for c in data["controls"]] == ["Save", "nameEdit"]
    assert data["controls"][1]["name"] == "Name"
    with pytest.raises(LookupError):
        capture.control_bounds("My App", only=["Nope"])


def test_split_path_handles_quotes_and_options():
    assert capture.split_path('a/b.png in Notepad') == ("a/b.png", "in Notepad")
    assert capture.split_path('"my dir/a b.png" only Save') == ("my dir/a b.png", "only Save")
    assert capture.split_path("x.json") == ("x.json", "")
    with pytest.raises(capture.CaptureError):
        capture.split_path("   ")
    assert script._options("My App pad=8", "pad", "fps") == ("My App", {"pad": 8})
    assert script._options("in My App fps=10 pad=2", "pad", "fps") == ("in My App", {"pad": 2, "fps": 10})
    assert script._split_in("only A, B in My App") == ("only A, B", "My App")
    assert script._split_in("") == ("", None)


def test_ffmpeg_command_windows_uses_gdigrab_with_even_size():
    cmd = capture.ffmpeg_command("out.mp4", (-20, 30, 1281, 799), fps=12, ffmpeg="ff", platform="win32")
    assert cmd[0] == "ff"
    assert cmd[cmd.index("-f") + 1] == "gdigrab"
    assert cmd[cmd.index("-video_size") + 1] == "1280x798"
    assert cmd[cmd.index("-offset_x") + 1] == "-20" and cmd[cmd.index("-offset_y") + 1] == "30"
    assert cmd[cmd.index("-framerate") + 1] == "12"
    assert "libx264" in cmd and "yuv420p" in cmd and cmd[-1] == "out.mp4"


def test_ffmpeg_command_linux_uses_x11grab_and_formats():
    cmd = capture.ffmpeg_command("out.webm", (10, 20, 800, 600), ffmpeg="ff", platform="linux", display=":99")
    assert cmd[cmd.index("-f") + 1] == "x11grab"
    assert cmd[cmd.index("-i") + 1] == ":99+10,20"
    assert "libvpx-vp9" in cmd
    assert any("palettegen" in a for a in capture.ffmpeg_command("o.gif", (0, 0, 10, 10), platform="linux"))
    assert "-draw_mouse" in cmd and cmd[cmd.index("-draw_mouse") + 1] == "1"
    with pytest.raises(capture.CaptureError):
        capture.ffmpeg_command("o.avi", (0, 0, 10, 10), platform="linux")


def test_recording_lifecycle_with_a_fake_ffmpeg(tmp_path, monkeypatch):
    out = tmp_path / "sub" / "demo.mp4"

    class Proc:
        returncode = None

        class stdin:
            written = b""

            @classmethod
            def write(cls, b):
                cls.written += b

            @classmethod
            def flush(cls):
                pass

            @classmethod
            def close(cls):
                pass

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            out.write_bytes(b"x" * 2048)  # ffmpeg writes the file when it gets `q`

    seen = {}

    def fake_popen(cmd, **kw):
        seen["cmd"] = cmd
        return Proc()

    monkeypatch.setattr(capture, "ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr(capture.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(capture.time, "sleep", lambda s: None)
    monkeypatch.setattr(capture, "_check_on_screen", lambda *a, **k: None)
    monkeypatch.setattr(capture.screen, "session_type", lambda: "x11")
    monkeypatch.setattr(capture, "window_box", lambda window=None, pad=0, focus=True: (WINDOW, (100, 50, 640, 480)))
    msg = capture.start_recording(str(out), window="My App", fps=10)
    assert "recording window 'My App' 640x480 at 10 fps" in msg and capture.recording()
    with pytest.raises(capture.CaptureError, match="already recording"):
        capture.start_recording(str(out), window="My App")
    assert "saved" in capture.stop_recording() and Proc.stdin.written == b"q\n"
    assert not capture.recording()
    with pytest.raises(capture.CaptureError, match="no recording"):
        capture.stop_recording()


def test_start_recording_reports_an_ffmpeg_that_dies(tmp_path, monkeypatch):
    class Dead:
        returncode = 1
        stdin = None

        def poll(self):
            return 1

    monkeypatch.setattr(capture, "ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr(capture.subprocess, "Popen", lambda cmd, **kw: Dead())
    monkeypatch.setattr(capture.time, "sleep", lambda s: None)
    monkeypatch.setattr(capture, "_check_on_screen", lambda *a, **k: None)
    monkeypatch.setattr(capture.screen, "session_type", lambda: "x11")
    with pytest.raises(capture.CaptureError, match="stopped at start"):
        capture.start_recording(str(tmp_path / "a.mp4"), region=(0, 0, 100, 100))


def test_shot_and_bounds_steps_write_files(tmp_path, monkeypatch, fake_window):
    monkeypatch.setattr(capture, "capture_window", lambda window=None, pad=0, focus=True: Image.new("RGB", (64, 48), "red"))
    png = tmp_path / "out dir" / "w.png"
    assert "saved" in run_step(f'shot "{png}" in My App pad=3')
    assert Image.open(png).size == (64, 48)
    js = tmp_path / "b.json"
    assert "3 controls" in run_step(f"bounds {js} in My App")
    assert json.loads(js.read_text(encoding="utf-8"))["controls"][1]["name"] == "Save"
    assert "1 controls" in run_step(f"bounds {js} only Save in My App")
    with pytest.raises(StepError, match="no control named"):
        run_step(f"bounds {js} only Nope in My App")
    with pytest.raises(StepError, match="bounds takes"):
        run_step(f"bounds {js} Save")
    with pytest.raises(StepError, match="no recording"):
        run_step("record_stop")


def test_capture_errors_become_step_errors(monkeypatch):
    def boom(*a, **k):
        raise capture.CaptureError("window is minimized")
    monkeypatch.setattr(capture, "capture_window", boom)
    with pytest.raises(StepError, match="minimized"):
        run_step("shot x.png in Foo")
    with pytest.raises(StepError, match="shot_region needs"):
        run_step("shot_region x.png 1 2")


def test_new_steps_survive_split_script():
    assert split_script('shot "a b/c.png" in App; bounds x.json only A, B') == [
        'shot "a b/c.png" in App', "bounds x.json only A, B"]


def test_fill_vars_replaces_only_known_names():
    assert fill_vars("shot ${OUT}/a.png; type ${OTHER}", {"OUT": "d"}) == "shot d/a.png; type ${OTHER}"
    assert fill_vars("x", None) == "x"


def _args(files, **kw):
    return argparse.Namespace(files=files, var=kw.get("var", []), json=kw.get("json"), no_failure_shot=True)


def test_replay_exit_codes_and_json_report(tmp_path, monkeypatch):
    good, bad = tmp_path / "good.amk", tmp_path / "bad.amk"
    good.write_text("wait 0\n", encoding="utf-8")
    bad.write_text("jump 1 2\n", encoding="utf-8")
    monkeypatch.setattr("automonkey.ai.screen.grab", lambda: Image.new("RGB", (10, 10)))
    report = tmp_path / "r" / "report.json"
    assert cli._replay_files(_args([str(good)], json=str(report))) == 0
    assert cli._replay_files(_args([str(good), str(bad)])) == 1
    assert cli._replay_files(_args([str(good), str(tmp_path / "missing.amk")])) == 2
    assert cli._replay_files(_args([str(good)], var=["novalue"])) == 2
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["passed"] == 1 and data["failed"] == 0 and data["scripts"][0]["file"] == str(good)


def test_x11_frame_uses_xwininfo_and_frame_extents(monkeypatch):
    from automonkey.ai import windows
    out = {
        "xwininfo": "  Absolute upper-left X:  462\n  Absolute upper-left Y:  292\n  Width: 1000\n  Height: 678\n",
        "xprop": "_NET_FRAME_EXTENTS(CARDINAL) = 1, 1, 22, 1\n",
    }
    monkeypatch.setattr(windows, "_run", lambda *a: out[a[0]])
    monkeypatch.setattr(windows.shutil, "which", lambda n: "/usr/bin/" + n)
    windows._extents_cache.clear()
    assert windows._x11_frame(99) == (461, 270, 1002, 701)
    monkeypatch.setattr(windows.shutil, "which", lambda n: None)
    assert windows._x11_frame(98) is None  # no xwininfo: the caller keeps wmctrl's numbers
