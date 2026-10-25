"""GUI automation test target built with PySide6.

This window is intentionally a *test target* for GUI automation tooling
(AutoMonkey and friends).  It contains three DELIBERATE BUGS so that
automated visual / behavioural tests can prove they find real bugs:

1. File > Export... (actionExport) is connected to nothing: triggering it
   does absolutely nothing (no dialog, no status update).
2. Edit > Preferences... (actionPrefs) sets a broken tab order:
   prefUser -> OK button -> prefEmail -> prefDark, so keyboard navigation
   jumps from the "User" field to the OK button before "Email".
3. The status bar label (statusLabel) has a fixed width of 140 px while its
   initial text is much longer, so the text is clipped.

Run with:  python tests/apps/qt_target.py
"""

import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class Canvas(QWidget):
    """Simple freehand drawing surface that records strokes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("canvas")
        self.setMinimumSize(400, 300)
        self.strokes: list[list[QPoint]] = []
        self._current: list[QPoint] | None = None
        self._label: QLabel | None = None

    def set_label(self, label: QLabel) -> None:
        self._label = label
        self._update_label()

    def point_count(self) -> int:
        return sum(len(stroke) for stroke in self.strokes)

    def clear(self) -> None:
        self.strokes = []
        self._current = None
        self._update_label()
        self.update()

    def _update_label(self) -> None:
        if self._label is not None:
            self._label.setText(
                f"Strokes: {len(self.strokes)}, points: {self.point_count()}"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._current = [event.position().toPoint()]
            self.strokes.append(self._current)
            self._update_label()
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._current is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._current.append(event.position().toPoint())
            self._update_label()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._current = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.setPen(QPen(QColor("black"), 2))
        for stroke in self.strokes:
            if len(stroke) == 1:
                painter.drawPoint(stroke[0])
            elif len(stroke) > 1:
                painter.drawPolyline(stroke)
        painter.setPen(QPen(QColor("black"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()


class TargetWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoMonkey Qt target")
        self.resize(1000, 720)

        self._count = 0

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    def _build_actions(self) -> None:
        self.actionNew = QAction("&New", self)
        self.actionNew.setObjectName("actionNew")
        self.actionNew.setShortcut("Ctrl+N")
        self.actionNew.triggered.connect(self.new_document)

        self.actionOpen = QAction("&Open...", self)
        self.actionOpen.setObjectName("actionOpen")
        self.actionOpen.setShortcut("Ctrl+O")
        self.actionOpen.triggered.connect(self.open_document)

        self.actionExport = QAction("&Export...", self)
        self.actionExport.setObjectName("actionExport")
        # DELIBERATE BUG: not connected to anything, does nothing.

        self.actionExit = QAction("E&xit", self)
        self.actionExit.setObjectName("actionExit")
        self.actionExit.setShortcut("Ctrl+Q")
        self.actionExit.triggered.connect(self.close)

        self.actionPrefs = QAction("&Preferences...", self)
        self.actionPrefs.setObjectName("actionPrefs")
        self.actionPrefs.triggered.connect(self.show_preferences)

        self.actionAbout = QAction("&About", self)
        self.actionAbout.setObjectName("actionAbout")
        self.actionAbout.triggered.connect(self.show_about)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.actionNew)
        file_menu.addAction(self.actionOpen)
        file_menu.addAction(self.actionExport)
        file_menu.addSeparator()
        file_menu.addAction(self.actionExit)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.actionPrefs)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(self.actionAbout)

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("Main", self)
        self.toolbar.setObjectName("toolbar")
        self.toolbar.addAction(self.actionNew)
        self.toolbar.addAction(self.actionOpen)
        self.addToolBar(self.toolbar)

    def _build_central(self) -> None:
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("splitter")
        self.setCentralWidget(self.splitter)

        # ---- left pane -------------------------------------------------
        left = QWidget(self.splitter)
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("Name:"))
        self.nameEdit = QLineEdit(left)
        self.nameEdit.setObjectName("nameEdit")
        self.nameEdit.setPlaceholderText("Your name")
        self.nameEdit.textChanged.connect(self._on_name_changed)
        left_layout.addWidget(self.nameEdit)

        self.greeting = QLabel("", left)
        self.greeting.setObjectName("greeting")
        left_layout.addWidget(self.greeting)

        self.incButton = QPushButton("Increment", left)
        self.incButton.setObjectName("incButton")
        self.incButton.clicked.connect(self.increment)
        left_layout.addWidget(self.incButton)

        self.countLabel = QLabel("Count: 0", left)
        self.countLabel.setObjectName("countLabel")
        left_layout.addWidget(self.countLabel)

        self.colorCombo = QComboBox(left)
        self.colorCombo.setObjectName("colorCombo")
        self.colorCombo.addItems(["Red", "Green", "Blue"])
        self.colorCombo.currentTextChanged.connect(self._on_color_changed)
        left_layout.addWidget(self.colorCombo)

        self.enabledCheck = QCheckBox("Enabled", left)
        self.enabledCheck.setObjectName("enabledCheck")
        left_layout.addWidget(self.enabledCheck)

        self.sourceList = QListWidget(left)
        self.sourceList.setObjectName("sourceList")
        self.sourceList.addItems(["Alpha", "Beta", "Gamma", "Delta"])
        self.sourceList.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        left_layout.addWidget(self.sourceList)

        self.msgButton = QPushButton("Show message", left)
        self.msgButton.setObjectName("msgButton")
        self.msgButton.clicked.connect(self.show_message)
        left_layout.addWidget(self.msgButton)

        left_layout.addStretch(1)

        # ---- right pane ------------------------------------------------
        right = QWidget(self.splitter)
        right_layout = QVBoxLayout(right)

        self.canvas = Canvas(right)
        right_layout.addWidget(self.canvas, 1)

        self.canvasLabel = QLabel("Strokes: 0, points: 0", right)
        self.canvasLabel.setObjectName("canvasLabel")
        right_layout.addWidget(self.canvasLabel)

        self.canvas.set_label(self.canvasLabel)

        self.splitter.addWidget(left)
        self.splitter.addWidget(right)

    def _build_status_bar(self) -> None:
        self.statusLabel = QLabel(
            "Ready - all systems operational and waiting for input", self
        )
        self.statusLabel.setObjectName("statusLabel")
        # DELIBERATE BUG: fixed width clips the long initial text.
        self.statusLabel.setFixedWidth(140)
        self.statusBar().addPermanentWidget(self.statusLabel)

    # ------------------------------------------------------------------
    # behaviour
    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        self.statusLabel.setText(text)

    def increment(self) -> None:
        self._count += 1
        self.countLabel.setText(f"Count: {self._count}")
        self.set_status(f"Count: {self._count}")

    def new_document(self) -> None:
        self._count = 0
        self.countLabel.setText("Count: 0")
        self.nameEdit.clear()
        self.canvas.clear()
        self.set_status("New document")

    def _on_name_changed(self, text: str) -> None:
        if text:
            self.greeting.setText(f"Hello, {text}!")
        else:
            self.greeting.setText("")

    def _on_color_changed(self, text: str) -> None:
        self.set_status(f"Color: {text}")

    def show_message(self) -> None:
        QMessageBox.information(self, "Message", "Button clicked")

    def show_about(self) -> None:
        QMessageBox.about(self, "About", "AutoMonkey Qt target v1")

    # ---- Open dialog ---------------------------------------------------
    def make_open_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setObjectName("openDialog")
        dialog.setWindowTitle("Open document")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        self.openPath = QLineEdit(dialog)
        self.openPath.setObjectName("openPath")
        layout.addWidget(self.openPath)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        return dialog

    def open_document(self) -> None:
        dialog = self.make_open_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_status(f"Opened {self.openPath.text()}")

    # ---- Preferences dialog -------------------------------------------
    def make_prefs_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setObjectName("prefsDialog")
        dialog.setWindowTitle("Preferences")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        self.prefUser = QLineEdit(dialog)
        self.prefUser.setObjectName("prefUser")
        form.addRow("User", self.prefUser)

        self.prefEmail = QLineEdit(dialog)
        self.prefEmail.setObjectName("prefEmail")
        form.addRow("Email", self.prefEmail)

        self.prefDark = QCheckBox("Dark mode", dialog)
        self.prefDark.setObjectName("prefDark")
        form.addRow(self.prefDark)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)

        # DELIBERATE BUG: tab order jumps to OK before Email.
        QWidget.setTabOrder(self.prefUser, ok_button)
        QWidget.setTabOrder(ok_button, self.prefEmail)
        QWidget.setTabOrder(self.prefEmail, self.prefDark)

        return dialog

    def show_preferences(self) -> None:
        dialog = self.make_prefs_dialog()
        dialog.exec()


def main() -> int:
    app = QApplication(sys.argv)
    window = TargetWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
