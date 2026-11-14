"""Unit tests for automonkey/ai/texttree.py against fake AT-SPI Text interfaces."""
from types import SimpleNamespace

import pytest

pytest.importorskip("pyautogui")

from automonkey.ai import texttree


def test_match_offsets_maps_back_through_folding():
    text = "Café  Noir\nDescription of how it is made"
    (s, e, whole), = texttree._match_offsets(text, "description of how")
    assert text[s:e] == "Description of how" and not whole
    (s, e, whole), = texttree._match_offsets(text, "cafe noir")
    assert text[s:e] == "Café  Noir"


def test_match_offsets_whole_and_none():
    assert texttree._match_offsets("Count: 2", "count: 2")[0][2] is True
    assert texttree._match_offsets("Count: 2", "missing") == []
    assert texttree._match_offsets("abc", "") == []


class FakeText:
    """Monospace text, 10x20 px per character, one line per \\n, at screen (100, 50)."""
    def __init__(self, text):
        self.text = text

    def get_character_count(self):
        return len(self.text)

    def get_text(self, a, b):
        return self.text[a:b]

    def _pos(self, i):
        line = self.text.count("\n", 0, i)
        col = i - (self.text.rfind("\n", 0, i) + 1)
        return 100 + col * 10, 50 + line * 20

    def get_range_extents(self, a, b, _coord):
        (x0, y0), (x1, y1) = self._pos(a), self._pos(b - 1)
        return SimpleNamespace(x=x0, y=y0, width=x1 + 10 - x0, height=y1 + 20 - y0)


def test_find_uses_character_extents(monkeypatch):
    iface = FakeText("Hello world\nDescription of how it is made")
    monkeypatch.setattr(texttree, "_atspi_texts", lambda w, r: iter([(iface, (90, 40, 600, 100))]))
    monkeypatch.setattr(texttree, "_atspi_visible_text", lambda i, r: (i.text, 0))
    monkeypatch.setattr(texttree, "screen", SimpleNamespace(view=lambda: SimpleNamespace(
        to_image=lambda x, y: (x, y), to_input=lambda x, y: (x, y))))
    monkeypatch.setattr(texttree, "_atspi_box", lambda i, s, e: (lambda a: (a.x, a.y, a.x + a.width, a.y + a.height))(
        i.get_range_extents(s, e, 0)))
    monkeypatch.setattr(texttree.sys, "platform", "linux")
    hits = texttree.find("w", "description of how")
    assert hits and (hits[0]["x"], hits[0]["y"], hits[0]["w"], hits[0]["h"]) == (100, 70, 180, 20)
    assert hits[0]["cx"] == 190 and hits[0]["text"] == "Description of how"
    assert texttree.find("w", "nothing like this") is None


class _FakeRange:
    """Minimal IUIAutomationTextRange over a string: [s, e) in characters."""
    def __init__(self, text, s=0, e=None):
        self.text, self.s, self.e = text, s, len(text) if e is None else e

    def GetText(self, _n):
        return self.text[self.s:self.e]

    def Clone(self):
        return _FakeRange(self.text, self.s, self.e)

    def MoveEndpointByRange(self, _endpoint, other, _src):
        self.e = other.s            # End := Start of the other range

    def Move(self, _unit, n):
        self.s += n
        self.e += n

    def MoveEndpointByUnit(self, _endpoint, _unit, n):
        self.e += n

    def GetBoundingRectangles(self):
        return [100.0 + self.s * 10, 50.0, (self.e - self.s) * 10.0, 16.0]


def test_uia_find_uses_offsets_when_findtext_is_missing(monkeypatch):
    """Qt's TextPattern.FindText returns NULL: occurrences are located in the visible text."""
    text = "Hello WYSIWYG title"
    vis = _FakeRange(text)

    class Visible:
        Length = 1
        def GetElement(self, _i):
            return vis

    class Pattern:
        def GetVisibleRanges(self):
            return Visible()

    class View:
        def to_image(self, x, y):
            return int(x), int(y)

    monkeypatch.setattr(texttree, "_uia_patterns", lambda w, r: iter([(Pattern(), (0, 0, 1000, 100))]))
    monkeypatch.setattr(texttree.screen, "view", lambda: View())
    hits = texttree._uia_find("w", "wysiwyg title", None)
    assert len(hits) == 1 and hits[0]["text"] == "WYSIWYG title"
    assert (hits[0]["x"], hits[0]["w"]) == (160, 130)
    assert texttree._uia_find("w", "absent", None) == []
