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
      - Hold Space (or middle mouse): pan
      - F: fit image to window
      - R: reset zoom (100%)

    Returns points as centered pixel coords (+y up), order = click order.
    """
    def __init__(self, img_path: str, max_points: int = 4):
        api, QtCore, QtGui, QtWidgets = _load_qt()
        self._QtCore, self._QtGui, self._QtWidgets = QtCore, QtGui, QtWidgets

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

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

        # ---- Dialog instead of QMainWindow ----
        self.dialog = QtWidgets.QDialog()
        self.dialog.setWindowTitle(f"Point Picker — {Path(img_path).name}")
        self.dialog.resize(1200, 850)
        self.dialog.keyPressEvent = self._on_key
        self.dialog.keyReleaseEvent = self._on_key_release

        # Create central widget layout
        layout = QtWidgets.QVBoxLayout(self.dialog)

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
        self.view.mouseReleaseEvent = self._on_mouse_release
        self.view.setCursor(QtCore.Qt.CrossCursor)

        layout.addWidget(self.view)

        # ---- Status label (instead of statusBar) ----
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 4px; background-color: #f0f0f0;")
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
        base = "Click to add points (TL, TR, BL, BR). Backspace=undo, S=save, Q/Esc=cancel, Wheel=zoom, Space-drag=pan, F=fit, R=reset."
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

    def _on_mouse_release(self, event):
        if self.view.dragMode() == self._QtWidgets.QGraphicsView.ScrollHandDrag:
            self.view.setDragMode(self._QtWidgets.QGraphicsView.NoDrag)
            self.view.viewport().setCursor(self._QtCore.Qt.CrossCursor)
        return self._QtWidgets.QGraphicsView.mouseReleaseEvent(self.view, event)

    def _on_key(self, event):
        QtCore = self._QtCore
        k = event.key()
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

    def run(self) -> List[Tuple[float, float]]:
        # Use QDialog's built-in exec() - this handles modal dialogs properly
        # and is designed to be created/destroyed repeatedly
        result = self.dialog.exec()

        # If dialog was accepted (S key or close with all points), return points
        if result == self._QtWidgets.QDialog.Accepted or (len(self.points) == self.max_points and self.saved):
            return list(self.points)
        else:
            return []


# Global variable to prevent multiple pickers from opening simultaneously
_picker_is_open = False

def pick_points_gui(image_file: str, max_points: int = 4) -> List[Tuple[float, float]]:
    global _picker_is_open

    # Prevent opening multiple pickers at once
    if _picker_is_open:
        print("WARNING: Picker already open, skipping...")
        return []

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
