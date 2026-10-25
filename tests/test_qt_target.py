import os, sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_APPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps")
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from qt_target import TargetWindow

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox


def _make_window(qtbot):
    window = TargetWindow()
    qtbot.addWidget(window)
    window.show()
    return window


def test_increment_twice_updates_count_label(qtbot):
    window = _make_window(qtbot)
    qtbot.mouseClick(window.incButton, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.incButton, Qt.MouseButton.LeftButton)
    assert window.countLabel.text() == "Count: 2"


def test_typing_name_updates_greeting(qtbot):
    window = _make_window(qtbot)
    qtbot.keyClicks(window.nameEdit, "Ana")
    assert window.greeting.text() == "Hello, Ana!"


def test_action_new_resets_count(qtbot):
    window = _make_window(qtbot)
    window.incButton.click()
    window.incButton.click()
    assert window.countLabel.text() == "Count: 2"
    window.actionNew.trigger()
    assert window.countLabel.text() == "Count: 0"
    assert window.nameEdit.text() == ""
    assert window.canvas.strokes == []


def test_combo_change_updates_status(qtbot):
    window = _make_window(qtbot)
    window.colorCombo.setCurrentText("Blue")
    assert window.statusLabel.text() == "Color: Blue"


def test_canvas_drag_creates_one_stroke(qtbot):
    window = _make_window(qtbot)
    canvas = window.canvas

    start = QPointF(10.0, 10.0)
    mid = QPointF(40.0, 40.0)
    end = QPointF(70.0, 20.0)

    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        start,
        canvas.mapToGlobal(start.toPoint()).toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        mid,
        canvas.mapToGlobal(mid.toPoint()).toPointF(),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        end,
        canvas.mapToGlobal(end.toPoint()).toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    canvas.mousePressEvent(press)
    canvas.mouseMoveEvent(move)
    canvas.mouseReleaseEvent(release)

    assert len(canvas.strokes) == 1
    assert canvas.point_count() == 2
    assert window.canvasLabel.text() == "Strokes: 1, points: 2"


def test_prefs_tab_order_has_known_bug(qtbot):
    window = _make_window(qtbot)
    dialog = window.make_prefs_dialog()
    # Do not register the dialog with qtbot: it is parented to the window and
    # is destroyed together with it, so pytest-qt must not close it later.

    ok_button = dialog.findChild(QDialogButtonBox).button(
        QDialogButtonBox.StandardButton.Ok
    )
    assert ok_button is not None

    chain = []
    widget = window.prefUser.nextInFocusChain()
    while widget is not window.prefUser and len(chain) < 50:
        chain.append(widget)
        widget = widget.nextInFocusChain()

    assert ok_button in chain
    assert window.prefEmail in chain
    # Known bug: OK comes before Email in the focus chain.
    assert chain.index(ok_button) < chain.index(window.prefEmail)


def test_about_box_called_with_title(qtbot, monkeypatch):
    window = _make_window(qtbot)
    calls = []

    def fake_about(parent, title, text):
        calls.append((title, text))

    monkeypatch.setattr(QMessageBox, "about", staticmethod(fake_about))
    window.actionAbout.trigger()

    assert len(calls) == 1
    assert calls[0][0] == "About"
    assert calls[0][1] == "AutoMonkey Qt target v1"


def test_message_box_called_with_title(qtbot, monkeypatch):
    window = _make_window(qtbot)
    calls = []

    def fake_information(parent, title, text):
        calls.append((title, text))

    monkeypatch.setattr(QMessageBox, "information", staticmethod(fake_information))
    window.msgButton.click()

    assert len(calls) == 1
    assert calls[0][0] == "Message"
    assert calls[0][1] == "Button clicked"


def test_open_dialog_sets_status(qtbot, monkeypatch):
    window = _make_window(qtbot)

    def fake_exec(self):
        # The dialog is created by TargetWindow.make_open_dialog(), which
        # stores the QLineEdit on the window as ``openPath``.
        window.openPath.setText("doc.txt")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)
    window.actionOpen.trigger()

    assert window.statusLabel.text() == "Opened doc.txt"
