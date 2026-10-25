# Qt (PySide6 / PyQt): headless tests with pytest-qt

pytest-qt drives Qt widgets inside a real Qt event loop, but without showing a window. It covers widget logic, signals, dialogs, keyboard/mouse events sent by Qt itself, and widget screenshots. It cannot cover real OS input, the real window manager, native file dialogs, DPI scaling, the look on the user's machine, or drag between apps. Those belong to AutoMonkey (layer 2).

## Setup

```bash
pip install pytest pytest-qt
```

For CI, force Qt to use the offscreen platform. Set it before Qt is imported, usually in `conftest.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

Tell pytest-qt which Qt binding to use in `pytest.ini`:

```ini
[pytest]
qt_api = pyside6
```

PyQt5 and PyQt6 work the same way; use `qt_api = pyqt5` or `pyqt6` accordingly.

## Basic widget test

```python
from PySide6.QtWidgets import QPushButton

def test_button(qtbot):
    button = QPushButton("Click")
    qtbot.addWidget(button)
    button.click()
    assert button.text() == "Click"
```

`qtbot.addWidget` ensures the widget is closed and deleted after the test.

## Mouse and keyboard

```python
qtbot.mouseClick(button, Qt.LeftButton)
qtbot.keyClicks(line_edit, "hello")
qtbot.keyClick(widget, Qt.Key_S, Qt.ControlModifier)
```

These send Qt events directly to the widget. They do not go through the OS.

## Signals and waiting

```python
with qtbot.waitSignal(signal, timeout=1000):
    action.trigger()
```

```python
qtbot.waitUntil(lambda: label.text() == "done", timeout=1000)
```

Use `waitSignal` for a specific signal, `waitUntil` for a condition.

## Menu actions

Find a `QAction` by object name and trigger it directly:

```python
action = window.findChild(QAction, "actionSave")
action.trigger()
```

This tests the connected slot without needing a real menu click.

## Modal dialogs

A modal dialog blocks the test. Patch it, or close it with a timer.

Patch `QMessageBox.question`:

```python
def test_confirm(monkeypatch, qtbot):
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.Yes)
    )
    # trigger the code that calls QMessageBox.question
```

For a custom modal dialog, accept it from a timer:

```python
QTimer.singleShot(0, lambda: dialog.accept())
# now open the dialog modally
```

## Tab order

Walk the focus chain and compare object names:

```python
from PySide6.QtCore import Qt

def focus_order(first):
    """objectNames along the focus chain, starting at `first`. The chain is circular,
    so stop when it comes back; skip widgets that can't take Tab focus."""
    order, w = [first.objectName()], first.nextInFocusChain()
    while w is not first:
        if w.focusPolicy() & Qt.TabFocus and w.isVisibleTo(first.window()):
            order.append(w.objectName())
        w = w.nextInFocusChain()
    return order

assert focus_order(dialog.prefUser)[:3] == ["prefUser", "prefEmail", "prefDark"]
```

This checks the order Qt was told; AutoMonkey's `tab_order N` (layer 2) checks what
really happens when a user presses Tab in the running app.

## Drag simulation

```python
qtbot.mousePress(widget, Qt.LeftButton, pos=QPoint(10, 10))
qtbot.mouseMove(widget, pos=QPoint(50, 50))
qtbot.mouseRelease(widget, Qt.LeftButton, pos=QPoint(50, 50))
```

Note: `mouseMove` with a button held is unreliable in Qt's test framework. Prefer testing the drop handler directly by constructing a `QMimeData` and calling the handler.

## Golden screenshots

Grab the widget and compare to a stored PNG. Fix the widget size and style first so goldens are stable:

```python
app.setStyle("Fusion")
widget.resize(400, 300)
```

Fonts differ across OSes, so keep goldens per OS or compare with a tolerance.

Small helper:

```python
from pathlib import Path
from PySide6.QtGui import QImage

def assert_golden(widget, name, tolerance=0):
    path = Path("tests/golden") / f"{name}.png"
    actual = widget.grab().toImage()
    if os.environ.get("UPDATE_GOLDEN"):
        actual.save(str(path))
        return
    golden = QImage(str(path))
    if actual.size() != golden.size():
        actual.save(f"{name}.actual.png")
        raise AssertionError("size mismatch")
    diff = 0
    for y in range(actual.height()):
        for x in range(actual.width()):
            pa = actual.pixelColor(x, y)
            pg = golden.pixelColor(x, y)
            if (abs(pa.red() - pg.red()) > tolerance or
                abs(pa.green() - pg.green()) > tolerance or
                abs(pa.blue() - pg.blue()) > tolerance):
                diff += 1
    if diff:
        actual.save(f"{name}.actual.png")
        raise AssertionError(f"{diff} pixels differ")
```

Set `UPDATE_GOLDEN=1` to rewrite goldens.

## Checklist

Test these for every Qt UI:

- Every `QAction` triggers the right slot.
- Enabled/disabled states are correct.
- Dialogs accept and reject correctly.
- Validation messages appear when input is invalid.
- Keyboard shortcuts work.
- Tab order follows the intended flow.
- Long text is elided in labels.
- Window resize respects minimum sizes.

## tkinter and DearPyGui

tkinter can be tested headlessly-ish with `widget.invoke()`, `event_generate()`, and `root.update()`, but it still needs a display. On Linux CI use `xvfb-run`.

DearPyGui has no test harness. Separate logic from callbacks and unit-test the logic. For the UI itself, rely on AutoMonkey (layer 2). DearPyGui exposes no accessibility tree, so AutoMonkey must use OCR and pixels there.

## CI

Run:

```bash
pytest -q
```

On failure, upload `*.actual.png` as artifacts so the agent can inspect visual differences.
