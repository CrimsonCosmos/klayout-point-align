
# align_gui_aqua_qt.py — Trimmed main that composes tabs and wires the runner

from __future__ import annotations
import sys
import json
from pathlib import Path
from functools import lru_cache
from qt_compat import QtCore, QtGui, QtWidgets

from gui.align_tab import AlignTab
from gui.runner import ExternalRunner
from diagnostic_logger import init_logger

@lru_cache(maxsize=8)
def resource_path(rel_path: str) -> Path:
    """Return absolute path to bundled resource (PyInstaller-safe)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel_path

APP_TITLE = "Point Align v1.2"

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

class CosineWaveWidget(QtWidgets.QWidget):
    """Animated cosine wave that oscillates on hover."""

    def __init__(self, size=32, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.size = size

        # Wave parameters (precise measurements from icon.ico)
        # Thickness: 10% of box dimensions
        self.line_thickness = size * 0.10

        # First peak: 287/1080 from top
        self.first_peak_from_top = size * (287.0 / 1080.0)

        # Peak-to-trough height: 549/1080 of box
        self.peak_to_trough = size * (549.0 / 1080.0)

        # Second peak is 76/1080 lower than first peak
        self.second_peak_offset = size * (76.0 / 1080.0)

        # Second minimum is 36/1080 lower than first minimum
        self.second_min_offset = size * (36.0 / 1080.0)

        self.phase_offset = 0.0  # Current animation phase
        self.current_speed = 0.0  # Current animation speed (multiplier)
        self.is_animating = False
        self.is_returning = False
        self.is_triggered = False  # Triggered animation (on alignment complete)
        self.animation_start_time = 0.0  # Time when animation started
        self.deceleration_start_time = 0.0  # Time when deceleration started
        self.deceleration_start_speed = 0.0  # Speed when deceleration started
        self.target_cycles = 0  # Number of cycles to complete for triggered animation
        self.completed_cycles = 0  # Number of cycles completed

        # Animation settings
        self.fps = 30
        self.wave_speed = 2.0  # seconds per cycle at full speed
        self.base_phase_increment = (2 * 3.14159) / (self.fps * self.wave_speed)
        self.acceleration_duration = 1.5  # seconds to reach full speed (hover)
        self.max_speed = 1.0  # Maximum speed multiplier (hover)

        # Triggered animation settings (on alignment complete)
        self.triggered_acceleration_duration = 1.5 / 4.0  # 4x faster acceleration
        self.triggered_max_speed = 4.0  # 4x speed multiplier

        # Animation timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update_animation)

        # Enable mouse tracking for hover
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def trigger_alignment_animation(self):
        """Trigger animation for alignment completion (3 cycles, 4x speed)."""
        import time
        # Don't trigger if already in a triggered animation
        if self.is_triggered:
            return

        self.is_triggered = True
        self.is_animating = True
        self.is_returning = False
        self.animation_start_time = time.time()
        self.target_cycles = 3
        self.completed_cycles = 0
        self.phase_offset = 0.0
        if not self.timer.isActive():
            self.timer.start(1000 // self.fps)

    def enterEvent(self, event):
        """Start animation with acceleration when mouse enters."""
        import time
        # Don't override triggered animation
        if self.is_triggered:
            return

        self.is_animating = True
        self.is_returning = False
        self.animation_start_time = time.time()
        if not self.timer.isActive():
            self.timer.start(1000 // self.fps)

    def leaveEvent(self, event):
        """Start deceleration when mouse leaves."""
        import time
        # Don't override triggered animation
        if self.is_triggered:
            return

        self.is_animating = False
        self.is_returning = True
        self.deceleration_start_time = time.time()
        self.deceleration_start_speed = self.current_speed

    def _update_animation(self):
        """Update animation frame with acceleration/deceleration."""
        import time

        # Early exit: if nothing is happening, stop the timer immediately
        if not self.is_animating and not self.is_returning and not self.is_triggered:
            if self.timer.isActive():
                self.timer.stop()
            return

        if self.is_triggered:
            # Triggered animation: 3 cycles with 4x speed
            elapsed = time.time() - self.animation_start_time

            if self.is_animating:
                # Accelerate 4x faster
                if elapsed < self.triggered_acceleration_duration:
                    progress = elapsed / self.triggered_acceleration_duration
                    self.current_speed = progress * progress * progress * self.triggered_max_speed
                else:
                    self.current_speed = self.triggered_max_speed

                # Track phase for cycle counting
                old_phase = self.phase_offset
                self.phase_offset += self.base_phase_increment * self.current_speed

                # Check if we completed a cycle
                if old_phase < (2 * 3.14159) and self.phase_offset >= (2 * 3.14159):
                    self.completed_cycles += 1
                    if self.completed_cycles >= self.target_cycles:
                        # Start deceleration after 3 cycles
                        self.is_animating = False
                        self.is_returning = True
                        self.deceleration_start_time = time.time()
                        self.deceleration_start_speed = self.current_speed

                self.phase_offset = self.phase_offset % (2 * 3.14159)
                self.update()

            elif self.is_returning:
                # Decelerate at same rate as acceleration
                decel_elapsed = time.time() - self.deceleration_start_time

                if decel_elapsed < self.triggered_acceleration_duration:
                    progress = decel_elapsed / self.triggered_acceleration_duration
                    ease_out = 1.0 - ((1.0 - progress) ** 3)
                    self.current_speed = self.deceleration_start_speed * (1.0 - ease_out)
                else:
                    self.current_speed = 0.0

                self.phase_offset += self.base_phase_increment * self.current_speed

                # Check if we've stopped
                if self.phase_offset >= (2 * 3.14159) and self.current_speed < 0.05:
                    self.phase_offset = 0.0
                    self.current_speed = 0.0
                    self.is_returning = False
                    self.is_triggered = False
                    self.timer.stop()
                self.update()

        elif self.is_animating:
            # Normal hover animation
            elapsed = time.time() - self.animation_start_time
            if elapsed < self.acceleration_duration:
                progress = elapsed / self.acceleration_duration
                self.current_speed = progress * progress * progress * self.max_speed
            else:
                self.current_speed = self.max_speed

            self.phase_offset += self.base_phase_increment * self.current_speed
            self.phase_offset = self.phase_offset % (2 * 3.14159)
            self.update()

        elif self.is_returning:
            # Normal hover deceleration
            elapsed = time.time() - self.deceleration_start_time

            if elapsed < self.acceleration_duration:
                progress = elapsed / self.acceleration_duration
                ease_out = 1.0 - ((1.0 - progress) ** 3)
                self.current_speed = self.deceleration_start_speed * (1.0 - ease_out)
            else:
                self.current_speed = 0.0

            self.phase_offset += self.base_phase_increment * self.current_speed

            if self.phase_offset >= (2 * 3.14159) and self.current_speed < 0.05:
                self.phase_offset = 0.0
                self.current_speed = 0.0
                self.is_returning = False
                self.timer.stop()
            self.update()
        else:
            self.timer.stop()

    def paintEvent(self, event):
        """Draw the W-shaped wave with precise measurements."""
        import math

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Black background
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0))

        # White pen with precise thickness
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255), int(self.line_thickness))
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # Calculate key points for W shape
        # W shape has: peak1 -> trough1 -> peak2 -> trough2 -> peak3
        # Left peak (lowest position, smallest amplitude)
        # Middle peak (higher position, medium amplitude)
        # Right peak (highest position, largest amplitude)
        width = self.size

        # First peak (left side of W) - lowest position of all peaks
        first_peak_y = self.first_peak_from_top

        # First trough (first valley) - measured from first peak
        first_trough_y = first_peak_y + self.peak_to_trough

        # Second peak (middle of W) - 76/1080 HIGHER than first (closer to top)
        second_peak_y = first_peak_y - self.second_peak_offset

        # Second trough (second valley) - lower than first trough
        second_trough_y = first_trough_y + self.second_min_offset

        # Third peak (right side, off-screen edge) - even higher than middle peak
        # For now, make it same as middle peak (we can adjust if needed)
        third_peak_y = second_peak_y - self.second_peak_offset

        # Draw W shape with smooth curves using point-by-point rendering
        path = QtGui.QPainterPath()
        num_points = width * 4  # High resolution for smooth curve

        for i in range(num_points + 1):
            x = (i / num_points) * width
            t = i / num_points  # Progress from 0 to 1

            # Apply animation phase offset (shifts the wave horizontally)
            animated_t = (t + self.phase_offset / (2 * math.pi)) % 1.0

            # W shape: 4 segments with smoother easing (cubic easing instead of cosine)
            # Segment 1 (0 to 0.25): first peak down to first trough
            # Segment 2 (0.25 to 0.5): first trough up to second peak
            # Segment 3 (0.5 to 0.75): second peak down to second trough
            # Segment 4 (0.75 to 1.0): second trough up to third peak

            def smooth_step(t):
                """Smoother easing function (cubic hermite interpolation)"""
                return t * t * (3 - 2 * t)

            if animated_t < 0.25:
                # Segment 1: first peak -> first trough
                local_t = animated_t / 0.25  # 0 to 1
                ease_t = smooth_step(local_t)
                y = first_peak_y + (first_trough_y - first_peak_y) * ease_t

            elif animated_t < 0.5:
                # Segment 2: first trough -> second peak
                local_t = (animated_t - 0.25) / 0.25  # 0 to 1
                ease_t = smooth_step(local_t)
                y = first_trough_y + (second_peak_y - first_trough_y) * ease_t

            elif animated_t < 0.75:
                # Segment 3: second peak -> second trough
                local_t = (animated_t - 0.5) / 0.25  # 0 to 1
                ease_t = smooth_step(local_t)
                y = second_peak_y + (second_trough_y - second_peak_y) * ease_t

            else:
                # Segment 4: second trough -> third peak (ends at right edge)
                local_t = (animated_t - 0.75) / 0.25  # 0 to 1
                ease_t = smooth_step(local_t)
                y = second_trough_y + (third_peak_y - second_trough_y) * ease_t

            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        painter.drawPath(path)


class AquaHeader(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.dark_mode = False
        self.setFixedHeight(56)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        # Create animated wave widget instead of static icon
        self.wave_widget = CosineWaveWidget(size=32, parent=self)

    def set_dark_mode(self, enabled: bool):
        self.dark_mode = enabled
        self.update()

    def resizeEvent(self, event):
        """Position wave widget when header is resized."""
        super().resizeEvent(event)
        # Position wave widget in top-left with padding
        wave_y = (self.height() - 32) // 2
        self.wave_widget.move(16, wave_y)

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

        # Draw text (wave widget is drawn automatically as a child widget)
        x_offset = 16 + 32 + 8  # Padding + wave width + spacing
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

        self.verbose_action = view_menu.addAction("Verbose Debug Mode")
        self.verbose_action.setCheckable(True)
        self.verbose_action.setChecked(False)
        self.verbose_action.triggered.connect(self._toggle_verbose)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)
        self.header = AquaHeader(APP_TITLE)
        root.addWidget(self.header)

        # No tabs - single unified interface wrapped in scroll area
        # (All LYS editing features integrated into Align tab)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self.align_tab = AlignTab(self)
        scroll.setWidget(self.align_tab)
        root.addWidget(scroll, 1)

        # Pass wave widget reference to align tab for animation triggers
        self.align_tab.wave_widget = self.header.wave_widget

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
        # Notify align tab that alignment finished (will load .lys into editor if successful)
        self.align_tab.onAlignmentFinished(code)

    # Theme management
    def _toggle_theme(self, checked: bool):
        self._dark_mode = checked
        self._apply_theme()
        self._save_preferences()

    def _toggle_verbose(self, checked: bool):
        """Toggle verbose debug mode - show/hide debug window."""
        if checked:
            self.align_tab.show_debug_window()
        else:
            self.align_tab.hide_debug_window()

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
        """Handle window close event."""
        # Check if there are unaligned images
        if self.align_tab.has_unaligned_images():
            summary = self.align_tab.get_unaligned_summary()

            reply = QtWidgets.QMessageBox.question(
                self,
                "Unaligned Images",
                f"{summary}\n\nAre you sure you want to exit?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel
            )

            if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        event.accept()

def main():
    # Initialize diagnostic logger (file logging disabled in production)
    # Set enable_file_logging=True for debugging
    logger = init_logger(enable_file_logging=False)
    # logger.log_system_info()  # Commented out to reduce noise
    # logger.info("Starting Point Align GUI...")

    try:
        app = QtWidgets.QApplication(sys.argv)

        # Set application icon for taskbar and window
        icon_path = resource_path("icon.ico")
        if icon_path.exists():
            app_icon = QtGui.QIcon(str(icon_path))
            app.setWindowIcon(app_icon)

        # Windows: Set AppUserModelID for proper taskbar icon display
        if sys.platform == 'win32':
            try:
                import ctypes
                myappid = 'WangLab.PointAlign.GUI.1.1'  # Arbitrary string
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except:
                pass  # Not critical if it fails

        w = MainWin()

        # Also set icon on main window
        if icon_path.exists():
            w.setWindowIcon(app_icon)

        w.show()
        logger.info("GUI initialized successfully")
        sys.exit(app.exec())
    except Exception as e:
        logger.log_exception(e, "main application startup")
        raise

if __name__ == "__main__":
    main()
