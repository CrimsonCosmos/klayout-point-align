
# align_gui_aqua_qt.py — Trimmed main that composes tabs and wires the runner

from __future__ import annotations
import sys
import json
from pathlib import Path
from qt_compat import QtCore, QtGui, QtWidgets

from gui.align_tab import AlignTab
from gui.runner import ExternalRunner
from lys_editor_tab import LYSTab
from diagnostic_logger import init_logger

APP_TITLE = "Point Align v1.1"

DARK_STYLESHEET = """
QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
}

QMainWindow, QDialog {
    background-color: #2b2b2b;
}

QTabWidget::pane {
    border: 1px solid #3d3d3d;
    background-color: #2b2b2b;
}

QTabBar::tab {
    background-color: #3d3d3d;
    color: #e0e0e0;
    padding: 8px 16px;
    border: 1px solid #3d3d3d;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #2b2b2b;
    border-bottom: 2px solid #5c9fd8;
}

QTabBar::tab:hover {
    background-color: #3d3d3d;
}

QGroupBox {
    border: 1px solid #3d3d3d;
    margin-top: 10px;
    padding-top: 10px;
    color: #e0e0e0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #5c9fd8;
}

QPushButton {
    background-color: #3d3d3d;
    color: #e0e0e0;
    border: 1px solid #555555;
    padding: 6px 12px;
    border-radius: 3px;
}

QPushButton:hover {
    background-color: #4d4d4d;
    border: 1px solid #5c9fd8;
}

QPushButton:pressed {
    background-color: #2d2d2d;
}

QPushButton:disabled {
    background-color: #2d2d2d;
    color: #666666;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #1e1e1e;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    padding: 4px;
    selection-background-color: #5c9fd8;
}

QListWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    alternate-background-color: #252525;
}

QListWidget::item:selected {
    background-color: #5c9fd8;
    color: #ffffff;
}

QListWidget::item:hover {
    background-color: #3d3d3d;
}

QLabel {
    color: #e0e0e0;
    background-color: transparent;
}

QLabel[class="link"] {
    color: #5c9fd8;
}

QCheckBox, QRadioButton {
    color: #e0e0e0;
    spacing: 5px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #555555;
    background-color: #1e1e1e;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #5c9fd8;
}

QComboBox {
    background-color: #3d3d3d;
    color: #e0e0e0;
    border: 1px solid #555555;
    padding: 4px;
}

QComboBox:hover {
    border: 1px solid #5c9fd8;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #2b2b2b;
    color: #e0e0e0;
    selection-background-color: #5c9fd8;
}

QSpinBox, QDoubleSpinBox {
    background-color: #1e1e1e;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
    padding: 4px;
}

QProgressBar {
    background-color: #1e1e1e;
    border: 1px solid #3d3d3d;
    text-align: center;
    color: #e0e0e0;
}

QProgressBar::chunk {
    background-color: #5c9fd8;
}

QMenuBar {
    background-color: #2b2b2b;
    color: #e0e0e0;
}

QMenuBar::item:selected {
    background-color: #3d3d3d;
}

QMenu {
    background-color: #2b2b2b;
    color: #e0e0e0;
    border: 1px solid #3d3d3d;
}

QMenu::item:selected {
    background-color: #5c9fd8;
}

QScrollBar:vertical {
    background-color: #2b2b2b;
    width: 12px;
}

QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #666666;
}

QScrollBar:horizontal {
    background-color: #2b2b2b;
    height: 12px;
}

QScrollBar::handle:horizontal {
    background-color: #555555;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #666666;
}
"""

class AquaHeader(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.dark_mode = False
        self.setFixedHeight(56)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        # Load the icon
        icon_path = Path(__file__).parent / "icon.ico"
        self.icon = QtGui.QPixmap(str(icon_path)) if icon_path.exists() else None

    def set_dark_mode(self, enabled: bool):
        self.dark_mode = enabled
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        rect = self.rect()
        grad = QtGui.QLinearGradient(0, 0, 0, rect.height())
        if self.dark_mode:
            grad.setColorAt(0.0, QtGui.QColor("#1e1e1e"))
            grad.setColorAt(0.5, QtGui.QColor("#2b2b2b"))
            grad.setColorAt(1.0, QtGui.QColor("#3d3d3d"))
            text_color = QtGui.QColor("#e0e0e0")
        else:
            grad.setColorAt(0.0, QtGui.QColor("#eaf2ff"))
            grad.setColorAt(0.5, QtGui.QColor("#d9e6ff"))
            grad.setColorAt(1.0, QtGui.QColor("#cddcff"))
            text_color = QtGui.QColor("#2a2a2a")
        p.fillRect(rect, grad)
        pen = QtGui.QPen(text_color)
        p.setPen(pen)
        font = QtGui.QFont("Lucida Grande", 13)
        if "Lucida Grande" not in QtGui.QFontDatabase().families():
            font = QtGui.QFont("Segoe UI Semibold", 12)
        p.setFont(font)

        # Draw icon and text
        x_offset = 16
        if self.icon and not self.icon.isNull():
            # Scale icon to fit header height with some padding
            icon_size = 32  # Slightly smaller than header height for nice padding
            scaled_icon = self.icon.scaled(
                icon_size, icon_size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            # Center icon vertically
            icon_y = (rect.height() - icon_size) // 2
            p.drawPixmap(x_offset, icon_y, scaled_icon)
            x_offset += icon_size + 8  # Add spacing after icon

        p.drawText(
            QtCore.QRect(x_offset, 0, rect.width() - x_offset - 16, rect.height()),
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
            self.title,
        )

class MainWin(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1100, 840)
        self._prefs_file = Path(__file__).parent / "gui_prefs.json"
        self._dark_mode = False

        # Create menu bar
        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")
        self.theme_action = view_menu.addAction("🌙 Dark Mode")
        self.theme_action.setCheckable(True)
        self.theme_action.triggered.connect(self._toggle_theme)

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

        # Load saved theme preference
        self._load_preferences()

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

    # Theme management
    def _toggle_theme(self, checked: bool):
        self._dark_mode = checked
        self._apply_theme()
        self._save_preferences()

    def _apply_theme(self):
        app = QtWidgets.QApplication.instance()
        if self._dark_mode:
            app.setStyleSheet(DARK_STYLESHEET)
            self.theme_action.setText("☀️ Light Mode")
        else:
            app.setStyleSheet("")
            self.theme_action.setText("🌙 Dark Mode")
        self.header.set_dark_mode(self._dark_mode)

    def _load_preferences(self):
        try:
            if self._prefs_file.exists():
                with open(self._prefs_file, 'r') as f:
                    prefs = json.load(f)
                    self._dark_mode = prefs.get('dark_mode', False)
                    self.theme_action.setChecked(self._dark_mode)
                    self._apply_theme()
        except Exception:
            pass

    def _save_preferences(self):
        try:
            prefs = {'dark_mode': self._dark_mode}
            with open(self._prefs_file, 'w') as f:
                json.dump(prefs, f)
        except Exception:
            pass

    def closeEvent(self, event):
        """Handle window close event - prompt if there are unsaved changes."""
        if self.lys_tab.has_unsaved_changes():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in the .LYS editor.\n\nDo you want to save before closing?",
                QtWidgets.QMessageBox.StandardButton.Save |
                QtWidgets.QMessageBox.StandardButton.Discard |
                QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Save
            )

            if reply == QtWidgets.QMessageBox.StandardButton.Save:
                # Try to save both editors if they have unsaved changes
                if self.lys_tab.left.has_unsaved_changes():
                    if self.lys_tab.left._current_path:
                        self.lys_tab.left.save()
                    else:
                        self.lys_tab.left.save_as()
                        # If user cancelled save dialog, cancel close
                        if self.lys_tab.left.has_unsaved_changes():
                            event.ignore()
                            return

                if self.lys_tab._dual_created and self.lys_tab.right and self.lys_tab.right.has_unsaved_changes():
                    if self.lys_tab.right._current_path:
                        self.lys_tab.right.save()
                    else:
                        self.lys_tab.right.save_as()
                        # If user cancelled save dialog, cancel close
                        if self.lys_tab.right.has_unsaved_changes():
                            event.ignore()
                            return

                event.accept()
            elif reply == QtWidgets.QMessageBox.StandardButton.Discard:
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()

def main():
    # Initialize diagnostic logger
    logger = init_logger()
    logger.log_system_info()
    logger.info("Starting Point Align GUI...")

    try:
        app = QtWidgets.QApplication(sys.argv)
        w = MainWin()
        w.show()
        logger.info("GUI initialized successfully")
        sys.exit(app.exec())
    except Exception as e:
        logger.log_exception(e, "main application startup")
        raise

if __name__ == "__main__":
    main()
