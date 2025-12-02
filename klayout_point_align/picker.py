# klayout_point_align/picker.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple

# Mouse-wheel zoom strength:
# Previously 1.32. To make scrolling feel ~175% as strong, we scaled (step-1) by 1.75:
# new_step = 1 + 1.75*(1.32 - 1) = 1.56
ZOOM_STEP = 1.56

def _load_qt():
    """
    Import Qt bindings via qt_compat (supports both PyQt6 and PySide6).
    """
    try:
        import sys
        from pathlib import Path
        # Add parent directory to path to find qt_compat
        parent_dir = Path(__file__).resolve().parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        from qt_compat import QtCore, QtGui, QtWidgets, USING_PYQT6, USING_PYSIDE6
        binding = "pyqt6" if USING_PYQT6 else "pyside6"
        return binding, QtCore, QtGui, QtWidgets
    except Exception as e:
        raise RuntimeError(
            "Could not import qt_compat. Please ensure PyQt6 or PySide6 is installed."
        ) from e


class _ImagePickerWidget(object):
    """
    Zoomable/pannable image picker using QGraphicsView in a QDialog.

    Controls:
      - Left-click: add point (max_points)
      - Backspace: undo last point
      - S: save (must have exactly max_points)
      - Q or Esc: cancel without saving
      - Mouse wheel / trackpad: zoom (under mouse)
      - Right-click, middle-click, or Space+drag: pan
      - F: fit image to window
      - R: reset zoom (100%)

    Returns points as centered pixel coords (+y up), order = click order.
    """
    def __init__(self, img_path: str, max_points: int = 4):
        api, QtCore, QtGui, QtWidgets = _load_qt()
        self._QtCore, self._QtGui, self._QtWidgets = QtCore, QtGui, QtWidgets
        self._qt_api = api  # Store which Qt binding we're using

        # Enable HiDPI scaling before creating QApplication (Qt5/PySide6 only; removed in Qt6)
        if QtWidgets.QApplication.instance() is None:
            if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
                QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
            if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
                QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

        self.img_path = str(img_path)
        self.max_points = max_points
        self.points: List[Tuple[float, float]] = []  # centered coords (+y up)
        self.saved = False
        self._panning_with_space = False
        self._panning_with_right = False
        self._last_pan_pos = None

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

        # ---- Dialog instead of QMainWindow ----
        self.dialog = QtWidgets.QDialog()
        self.dialog.setWindowTitle(f"Point Picker — {Path(img_path).name}")

        # Size window to fit available screen space (accounting for taskbar)
        screen = self.app.primaryScreen()
        if screen:
            available_geom = screen.availableGeometry()  # Excludes taskbar
            # Use 95% of available height and 90% of width, with max constraints
            target_width = min(1200, int(available_geom.width() * 0.9))
            target_height = min(850, int(available_geom.height() * 0.95))
            self.dialog.resize(target_width, target_height)
        else:
            self.dialog.resize(1200, 850)

        self.dialog.keyPressEvent = self._on_key
        self.dialog.keyReleaseEvent = self._on_key_release

        # Create central widget layout
        layout = QtWidgets.QVBoxLayout(self.dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- Scene & View ----
        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.view.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        self.view.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self.view.wheelEvent = self._on_wheel
        self.view.mousePressEvent = self._on_mouse_press
        self.view.mouseMoveEvent = self._on_mouse_move
        self.view.mouseReleaseEvent = self._on_mouse_release
        self.view.setCursor(QtCore.Qt.CrossCursor)

        layout.addWidget(self.view)

        # ---- Create floating overlay controls panel (top-right) ----
        # Create as child of dialog for absolute positioning
        self.controls_panel = QtWidgets.QGroupBox("Display (↑↓ ←→)", self.dialog)
        self.controls_panel.setMaximumWidth(220)
        self.controls_panel.setStyleSheet("""
            QGroupBox {
                background-color: rgba(240, 240, 240, 220);
                border: 2px solid #999;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 8px;
                font-size: 8pt;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
            }
        """)
        controls_layout = QtWidgets.QFormLayout(self.controls_panel)
        controls_layout.setContentsMargins(6, 4, 6, 6)
        controls_layout.setSpacing(2)
        controls_layout.setLabelAlignment(QtCore.Qt.AlignRight)

        # Helper to create compact slider row
        def create_compact_slider(label, range_min, range_max, default_val, label_text):
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(range_min, range_max)
            slider.setValue(default_val)
            slider.setMaximumWidth(130)
            value_label = QtWidgets.QLabel(label_text)
            value_label.setMinimumWidth(30)
            value_label.setAlignment(QtCore.Qt.AlignRight)
            value_label.setStyleSheet("font-size: 8pt;")
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            row.addWidget(slider)
            row.addWidget(value_label)
            label_widget = QtWidgets.QLabel(label)
            label_widget.setStyleSheet("font-size: 8pt;")
            controls_layout.addRow(label_widget, row)
            return slider, value_label

        # Create all sliders
        self.brightness_slider, self.brightness_label = create_compact_slider("Bright:", -100, 100, 0, "0")
        self.contrast_slider, self.contrast_label = create_compact_slider("Contrast:", -100, 100, 0, "0")
        self.gamma_slider, self.gamma_label = create_compact_slider("Gamma:", 30, 300, 100, "1.00")
        self.red_slider, self.red_label = create_compact_slider("Red:", 0, 200, 100, "1.00")
        self.green_slider, self.green_label = create_compact_slider("Green:", 0, 200, 100, "1.00")
        self.blue_slider, self.blue_label = create_compact_slider("Blue:", 0, 200, 100, "1.00")

        # Position the panel at top-right corner
        self.controls_panel.move(10, 10)
        self.controls_panel.raise_()  # Bring to front
        self.controls_panel.show()

        # Connect sliders
        self.brightness_slider.valueChanged.connect(self._update_display)
        self.contrast_slider.valueChanged.connect(self._update_display)
        self.gamma_slider.valueChanged.connect(self._update_display)
        self.red_slider.valueChanged.connect(self._update_display)
        self.green_slider.valueChanged.connect(self._update_display)
        self.blue_slider.valueChanged.connect(self._update_display)

        # Force panel to resize to fit all sliders
        self.controls_panel.adjustSize()

        # Track which slider is focused for keyboard control
        self.focused_slider_index = 0
        self.sliders = [self.brightness_slider, self.contrast_slider, self.gamma_slider,
                        self.red_slider, self.green_slider, self.blue_slider]

        # ---- Status label (instead of statusBar) ----
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 4px; background-color: #f0f0f0; font-size: 9pt;")
        layout.addWidget(self.status_label)
        self._update_status()

        # ---- Load image ----
        self._img = QtGui.QImage(self.img_path)
        if self._img.isNull():
            raise RuntimeError(f"Could not load image: {img_path}")
        self._pix = QtGui.QPixmap.fromImage(self._img)
        self._pix_item = QtWidgets.QGraphicsPixmapItem(self._pix)
        self._pix_item.setZValue(0)
        self.scene.addItem(self._pix_item)

        self.img_w = self._pix.width()
        self.img_h = self._pix.height()

        # ---- Crosshair at image center ----
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 120))
        pen.setWidth(0)  # cosmetic
        self._line_v = self.scene.addLine(self.img_w/2, 0, self.img_w/2, self.img_h, pen)
        self._line_h = self.scene.addLine(0, self.img_h/2, self.img_w, self.img_h/2, pen)
        self._line_v.setZValue(5)
        self._line_h.setZValue(5)

        # Layer for points/labels
        self._point_items: list = []

        # Fit to window initially
        self._fit_to_view()

    # ----------------- Helpers -----------------
    def _update_status(self, msg: str | None = None):
        base = "Left-click to add points (TL, TR, BL, BR). Right-click to pan. Backspace=undo, S=save, Q/Esc=cancel, Wheel=zoom, F=fit, R=reset."
        if msg:
            self.status_label.setText(f"{base}  |  {msg}")
        else:
            self.status_label.setText(base)

    def _fit_to_view(self):
        self.view.fitInView(self._pix_item, self._QtCore.Qt.KeepAspectRatio)

    def _reset_zoom(self):
        self.view.resetTransform()
        self.view.centerOn(self._pix_item)

    def _view_to_image_xy(self, view_pos) -> Tuple[float, float]:
        scene_pt = self.view.mapToScene(view_pos)
        x = float(scene_pt.x())
        y = float(scene_pt.y())
        return x, y

    def _image_to_centered(self, x_tl: float, y_tl: float) -> Tuple[float, float]:
        cx = x_tl - self.img_w / 2.0
        cy = (self.img_h / 2.0) - y_tl
        return (cx, cy)

    def _centered_to_image(self, cx: float, cy: float) -> Tuple[float, float]:
        x = cx + self.img_w / 2.0
        y = self.img_h / 2.0 - cy
        return (x, y)

    def _redraw_points(self):
        # Remove old
        for it in self._point_items:
            self.scene.removeItem(it)
        self._point_items.clear()

        QtGui = self._QtGui

        # Style for the X
        pen_bg = QtGui.QPen(QtGui.QColor(0, 0, 0, 200))      # outline
        pen_bg.setWidthF(3.0)
        pen_fg = QtGui.QPen(QtGui.QColor(255, 255, 255, 230))  # main stroke
        pen_fg.setWidthF(1.6)
        arm = 8  # half-length of X arms in pixels

        for i, (cx, cy) in enumerate(self.points):
            x, y = self._centered_to_image(cx, cy)

            # 'X' (two crossing lines): dark underlay then light overlay
            l1_bg = self.scene.addLine(x - arm, y - arm, x + arm, y + arm, pen_bg)
            l1_fg = self.scene.addLine(x - arm, y - arm, x + arm, y + arm, pen_fg)
            l2_bg = self.scene.addLine(x - arm, y + arm, x + arm, y - arm, pen_bg)
            l2_fg = self.scene.addLine(x - arm, y + arm, x + arm, y - arm, pen_fg)

            for it in (l1_bg, l1_fg, l2_bg, l2_fg):
                it.setZValue(10)
                self._point_items.append(it)

            # Label next to the X
            lab = self.scene.addSimpleText(f"P{i} ({cx:.1f},{cy:.1f})")
            lab.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
            lab.setPos(x + arm + 6, y - arm - 6)
            lab.setZValue(11)
            self._point_items.append(lab)

    # ----------------- Events ------------------
    def _on_wheel(self, event):
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else 0
        if delta == 0 and hasattr(event, "pixelDelta"):
            delta = event.pixelDelta().y()
        if delta == 0:
            return
        zoom_in = delta > 0
        factor = ZOOM_STEP if zoom_in else (1.0 / ZOOM_STEP)
        self.view.scale(factor, factor)

    def _on_mouse_press(self, event):
        QtCore = self._QtCore

        # Right-click panning (manual implementation)
        if event.button() == QtCore.Qt.RightButton:
            self._panning_with_right = True
            self._last_pan_pos = event.pos()
            self.view.viewport().setCursor(QtCore.Qt.ClosedHandCursor)
            return

        # Middle-click or Space+Left-click panning (Qt's built-in drag mode)
        if event.button() == QtCore.Qt.MiddleButton or (event.button() == QtCore.Qt.LeftButton and self._panning_with_space):
            self.view.setDragMode(self._QtWidgets.QGraphicsView.ScrollHandDrag)
            self.view.viewport().setCursor(QtCore.Qt.ClosedHandCursor)
            return self._QtWidgets.QGraphicsView.mousePressEvent(self.view, event)

        if event.button() == QtCore.Qt.LeftButton:
            if len(self.points) >= self.max_points:
                self._update_status(f"Already have {self.max_points} points. Press Backspace to undo or S to save.")
                return
            x_tl, y_tl = self._view_to_image_xy(event.pos())
            if 0 <= x_tl < self.img_w and 0 <= y_tl < self.img_h:
                cx, cy = self._image_to_centered(x_tl, y_tl)
                self.points.append((cx, cy))
                self._redraw_points()
                self._update_status(f"Placed P{len(self.points)-1}")
                if len(self.points) == self.max_points:
                    self._update_status("Have all points. Press S to save.")
            else:
                self._update_status("Click inside the image area.")
            return

        return self._QtWidgets.QGraphicsView.mousePressEvent(self.view, event)

    def _on_mouse_move(self, event):
        # Handle right-click panning
        if self._panning_with_right and self._last_pan_pos is not None:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()

            # Get the current scrollbar values
            h_bar = self.view.horizontalScrollBar()
            v_bar = self.view.verticalScrollBar()

            # Pan by adjusting scrollbar positions (inverted delta for natural feel)
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            return

        return self._QtWidgets.QGraphicsView.mouseMoveEvent(self.view, event)

    def _on_mouse_release(self, event):
        # Handle right-click panning release
        if event.button() == self._QtCore.Qt.RightButton:
            self._panning_with_right = False
            self._last_pan_pos = None
            self.view.viewport().setCursor(self._QtCore.Qt.CrossCursor)
            return

        # Handle middle-click or Space+Left-click panning release
        if self.view.dragMode() == self._QtWidgets.QGraphicsView.ScrollHandDrag:
            self.view.setDragMode(self._QtWidgets.QGraphicsView.NoDrag)
            self.view.viewport().setCursor(self._QtCore.Qt.CrossCursor)
        return self._QtWidgets.QGraphicsView.mouseReleaseEvent(self.view, event)

    def _on_key(self, event):
        QtCore = self._QtCore
        k = event.key()

        # Arrow key navigation for sliders
        if k == QtCore.Qt.Key_Up:
            # Move to previous slider
            self.focused_slider_index = (self.focused_slider_index - 1) % len(self.sliders)
            self.sliders[self.focused_slider_index].setFocus()
            event.accept()
            return
        elif k == QtCore.Qt.Key_Down:
            # Move to next slider
            self.focused_slider_index = (self.focused_slider_index + 1) % len(self.sliders)
            self.sliders[self.focused_slider_index].setFocus()
            event.accept()
            return
        elif k == QtCore.Qt.Key_Left:
            # Decrease current slider value
            current_slider = self.sliders[self.focused_slider_index]
            current_slider.setValue(current_slider.value() - 1)
            event.accept()
            return
        elif k == QtCore.Qt.Key_Right:
            # Increase current slider value
            current_slider = self.sliders[self.focused_slider_index]
            current_slider.setValue(current_slider.value() + 1)
            event.accept()
            return

        if k == QtCore.Qt.Key_Backspace and self.points:
            self.points.pop()
            self._redraw_points()
            self._update_status("Undid last point.")
        elif k in (QtCore.Qt.Key_S,):
            if len(self.points) < self.max_points:
                self._update_status(f"Need {self.max_points} points; have {len(self.points)}.")
                return
            self.saved = True
            self.dialog.accept()
        elif k in (QtCore.Qt.Key_Q, QtCore.Qt.Key_Escape):
            self.points.clear()
            self.saved = False
            self.dialog.reject()
        elif k == QtCore.Qt.Key_F:
            self._fit_to_view()
        elif k == QtCore.Qt.Key_R:
            self._reset_zoom()
        elif k == QtCore.Qt.Key_Space:
            self._panning_with_space = True
            self.view.setDragMode(self._QtWidgets.QGraphicsView.ScrollHandDrag)
            self.view.viewport().setCursor(QtCore.Qt.ClosedHandCursor)

    def _on_key_release(self, event):
        if event.key() == self._QtCore.Qt.Key_Space:
            self._panning_with_space = False
            self.view.setDragMode(self._QtWidgets.QGraphicsView.NoDrag)
            self.view.viewport().setCursor(self._QtCore.Qt.CrossCursor)

    def _update_display(self):
        """Apply brightness/contrast/gamma/RGB adjustments to displayed image (not saved image)."""
        import numpy as np

        brightness = self.brightness_slider.value()  # -100 to +100
        contrast = self.contrast_slider.value() / 100.0  # -1.0 to +1.0
        gamma = self.gamma_slider.value() / 100.0  # 0.3 to 3.0
        red_mult = self.red_slider.value() / 100.0  # 0 to 2.0
        green_mult = self.green_slider.value() / 100.0  # 0 to 2.0
        blue_mult = self.blue_slider.value() / 100.0  # 0 to 2.0

        # Update labels
        self.brightness_label.setText(str(brightness))
        self.contrast_label.setText(str(self.contrast_slider.value()))
        self.gamma_label.setText(f"{gamma:.2f}")
        self.red_label.setText(f"{red_mult:.2f}")
        self.green_label.setText(f"{green_mult:.2f}")
        self.blue_label.setText(f"{blue_mult:.2f}")

        # Convert original QImage to 32-bit ARGB format for fast manipulation
        QtGui = self._QtGui
        adjusted = self._img.convertToFormat(QtGui.QImage.Format_ARGB32)

        # Get direct pointer to pixel data
        bits = adjusted.bits()
        # PyQt6 requires setsize() to be called on voidptr before using it
        # Check if setsize() method exists (PyQt6) or if we need it
        if hasattr(bits, 'setsize'):
            bits.setsize(adjusted.height() * adjusted.width() * 4)

        # Use numpy for fast vectorized operations
        arr = np.frombuffer(bits, dtype=np.uint8).reshape((adjusted.height(), adjusted.width(), 4))

        # Apply brightness/contrast/gamma/RGB to RGB channels (not alpha)
        rgb = arr[:, :, :3].astype(np.float32)

        # Apply contrast (scale around midpoint 127.5)
        if contrast != 0:
            # Contrast formula: (pixel - 127.5) * (1 + contrast) + 127.5
            rgb = (rgb - 127.5) * (1.0 + contrast) + 127.5

        # Apply brightness (simple addition)
        rgb += brightness

        # Apply gamma correction (if not 1.0)
        if abs(gamma - 1.0) > 0.01:
            # Normalize to 0-1 range, apply gamma, then scale back to 0-255
            rgb = np.clip(rgb, 0, 255)
            rgb = 255.0 * np.power(rgb / 255.0, gamma)

        # Apply RGB channel multipliers
        rgb[:, :, 0] *= red_mult    # Red channel
        rgb[:, :, 1] *= green_mult  # Green channel
        rgb[:, :, 2] *= blue_mult   # Blue channel

        # Clip to valid range
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        arr[:, :, :3] = rgb

        # Update displayed pixmap
        self._pix = QtGui.QPixmap.fromImage(adjusted)
        self._pix_item.setPixmap(self._pix)

    def _save_adjusted_image(self):
        """Save the adjusted image to replace the original, so .lys uses the adjusted version."""
        try:
            import cv2
            import numpy as np
            from pathlib import Path

            # Get the current adjusted pixmap
            adjusted_img = self._pix.toImage()

            # Convert QImage to numpy array
            bits = adjusted_img.bits()
            # PyQt6 requires setsize() to be called on voidptr before using it
            if hasattr(bits, 'setsize'):
                bits.setsize(adjusted_img.height() * adjusted_img.width() * 4)
            arr = np.frombuffer(bits, dtype=np.uint8).reshape((adjusted_img.height(), adjusted_img.width(), 4))

            # Convert BGRA to BGR for OpenCV
            bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

            # Save to the original file path, replacing it with adjusted version
            # Create backup first
            img_path = Path(self.img_path)
            backup_path = img_path.with_suffix(img_path.suffix + '.backup')

            # Only create backup if it doesn't already exist (preserve original)
            if not backup_path.exists():
                import shutil
                shutil.copy2(self.img_path, backup_path)

            # Save adjusted image
            cv2.imwrite(str(img_path), bgr)
            return True
        except ImportError as e:
            # If cv2 isn't available, show error but don't crash
            print(f"Warning: Could not save adjusted image - {e}")
            print("Continuing without saving adjusted image...")
            return False
        except Exception as e:
            print(f"Error saving adjusted image: {e}")
            return False

    def run(self) -> List[Tuple[float, float]]:
        # Use QDialog's built-in exec() - this handles modal dialogs properly
        # and is designed to be created/destroyed repeatedly
        result = self.dialog.exec()

        # If dialog was accepted (S key or close with all points), save adjusted image and return points
        if result == self._QtWidgets.QDialog.Accepted or (len(self.points) == self.max_points and self.saved):
            # Save the adjusted image to disk
            self._save_adjusted_image()
            return list(self.points)
        else:
            return []


# Global variable to prevent multiple pickers from opening simultaneously
_picker_is_open = False

def pick_points_gui(image_file: str, max_points: int = 4) -> List[Tuple[float, float]]:
    """
    Launch interactive point picker GUI.

    Returns:
        List[Tuple[float, float]] - picked point coordinates (centered)
    """
    global _picker_is_open

    # Prevent opening multiple pickers at once
    if _picker_is_open:
        print("WARNING: Picker already open, skipping...")
        return {'points': [], 'display': {}}

    try:
        _picker_is_open = True

        # Process any pending Qt events before opening picker
        api, QtCore, QtGui, QtWidgets = _load_qt()
        app = QtWidgets.QApplication.instance()
        if app:
            app.processEvents()

        picker = _ImagePickerWidget(image_file, max_points=max_points)
        result = picker.run()

        # Process events again after closing to ensure cleanup
        if app:
            app.processEvents()

        return result
    finally:
        _picker_is_open = False
