
# align_gui_aqua_qt.py — Trimmed main that composes tabs and wires the runner

from __future__ import annotations
import sys
from qt_compat import QtCore, QtGui, QtWidgets

from gui.align_tab import AlignTab
from gui.runner import ExternalRunner
from lys_editor_tab import LYSTab

APP_TITLE = "Point Align"

class AquaHeader(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setFixedHeight(56)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        rect = self.rect()
        grad = QtGui.QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, QtGui.QColor("#eaf2ff"))
        grad.setColorAt(0.5, QtGui.QColor("#d9e6ff"))
        grad.setColorAt(1.0, QtGui.QColor("#cddcff"))
        p.fillRect(rect, grad)
        pen = QtGui.QPen(QtGui.QColor("#2a2a2a"))
        p.setPen(pen)
        font = QtGui.QFont("Lucida Grande", 13)
        if "Lucida Grande" not in QtGui.QFontDatabase().families():
            font = QtGui.QFont("Segoe UI Semibold", 12)
        p.setFont(font)
        p.drawText(
            QtCore.QRect(16, 0, rect.width() - 32, rect.height()),
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
            self.title,
        )

class MainWin(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1100, 840)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)
        self.header = AquaHeader(APP_TITLE)
        root.addWidget(self.header)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        root.addWidget(self.tabs, 1)

        # Tab 1: Align
        self.align_tab = AlignTab(self)
        self.tabs.addTab(self.align_tab, "Align")

        # Tab 2: .LYS editing
        self.lys_tab = LYSTab(parent=self)
        self.tabs.addTab(self.lys_tab, ".LYS file editing")

        # Hook runRequested -> start worker
        self.align_tab.runRequested.connect(self._start_run)
        self._worker = None

    # Runner wiring
    def _start_run(self, argv: list):
        worker = ExternalRunner(argv, parent=self)
        worker.started_with_cmd.connect(self.align_tab.appendLog)
        worker.line_ready.connect(self.align_tab.insertPlain)
        worker.logfile_ready.connect(lambda p: self.align_tab.appendLog(f"[Log file] {p}\n"))
        worker.finished_with_code.connect(self._run_finished)
        self._worker = worker
        worker.start()

    def _run_finished(self, code: int):
        self.align_tab.setProgressVisible(False)
        self.align_tab.appendLog(f"\n[Process exited with code {code}]\n")

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWin(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
