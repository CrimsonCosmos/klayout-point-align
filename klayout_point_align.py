#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
klayout_point_align.py — combine point picking and alignment into ONE file.

What you get
------------
- pick_points_gui(...): A method that opens a GUI to pick 4 points on an image.
  It returns *centered* pixel coordinates (origin at image center, +x right, +y up).
- align_markers(...): A method that takes BEFORE_CTR_PX (picked points in centered px),
  AFTER_PTS_UM (target points in µm), and computes an affine or projective transform
  from pixels -> microns. It returns the transform matrix and RMS error. It also has
  an optional hook to update a KLayout .lys file (left as a stub for you to drop in
  your existing "build_value_text(...)" logic).
- run_combo(...): Opens the picker first and then immediately runs alignment using
  the picked points.

Better picker
-------------
- Mouse wheel (or trackpad) zoom (under the cursor)
- Hold Space and drag (or use middle mouse) to pan
- Left-click to add points, Backspace to undo, S to save, F to fit, R to reset, Q/Esc to cancel

CLI
---
Subcommands:
  pick   : pick points and save to JSON
  align  : read points from JSON (or argv) and compute the transform
  run    : pick and then align in one go

Examples
--------
One-shot: pick points and align immediately
$HOME/klayout-tools/venv/bin/python /Users/dylangehl/klayout-tools/klayout_point_align.py run \
  --image /Users/dylangehl/klayout-tools/IMG_2025_07_19_48116.JPG \
  --after "(-50,60),(70,60),(-50,-60),(70,-60)" \
  --affine-only

Drop-in method usage
--------------------
from klayout_point_align import pick_points_gui, align_markers, run_combo

pts_cxcy = pick_points_gui("/path/img.jpg")  # returns list[tuple[float,float]]
H_um, rms = align_markers(pts_cxcy, cfg=AlignConfig(after_pts_um=[...], affine_only=True))

Notes
-----
- "centered coordinates" means (0,0) is at image center; +y is up.
- If you want to *also* update the .lys session with an img::Object, put your
  original value-string generator into the stub `build_klayout_img_value(...)`.
- This file is self-contained and does NOT import your old scripts. It is meant
  to replace "pick_points.py" + "AlignMarkers.py" in a single, reusable module.
"""

# Optional auto-detect hook
try:
    from autodetect_fiducials import detect_four_points_centered, AutoParams  # new module
except Exception:
    detect_four_points_centered = None
    AutoParams = None  # type: ignore


import argparse
import ast
import json
import math
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np

# Global flags set by batch runner / CLI to control auto-detect behavior
_AUTO_FLAGS = (False, False)  # (use_auto_or_review, auto_review)
_AUTO_PARAMS = None           # Optional AutoParams instance


# ------------------------------
# Utility: parsing small tuples
# ------------------------------
def parse_pts(s: str) -> List[Tuple[float, float]]:
    """
    Parse points from a string like "(-50,60),(70,60),(-50,-60),(70,-60)".
    Returns list of (x,y) floats.
    """
    try:
        # Wrap in brackets if not already
        txt = s.strip()
        if not txt.startswith("["):
            txt = "[" + txt + "]"
        pts = ast.literal_eval(txt)
        out = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                out.append((float(p[0]), float(p[1])))
            else:
                raise ValueError("Each point must be a 2-tuple")
        return out
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Could not parse points: {e}")


# -----------------------------------------------
# Part 1: Point picking (zoom/pan QGraphicsView)
# -----------------------------------------------
def _load_qt():
    """
    Import Qt bindings (PyQt5 preferred, fallback to PySide6).
    We only import when needed so the module is importable without Qt.
    """
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
        return "pyqt5", QtCore, QtGui, QtWidgets
    except Exception:
        try:
            from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
            return "pyside6", QtCore, QtGui, QtWidgets
        except Exception as e:
            raise RuntimeError(
                "Neither PyQt5 nor PySide6 is available. Please install one of them."
            ) from e


class _ImagePickerWidget:
    """
    Zoomable/pannable image picker using QGraphicsView.
    Controls:
      - Left-click: add point (max_points)
      - Backspace: undo last point
      - S: save (must have exactly max_points)
      - Q or Esc: cancel without saving
      - Mouse wheel / trackpad: zoom
      - Hold Space (or middle mouse): pan
      - F: fit image to window
      - R: reset zoom (100%)
    Returns points as centered pixel coords (+y up), order = click order.
    """
    def __init__(self, img_path: str, max_points: int = 4):
        api, QtCore, QtGui, QtWidgets = _load_qt()
        self._QtCore, self._QtGui, self._QtWidgets = QtCore, QtGui, QtWidgets

        # Enable HiDPI scaling on macOS/retina before creating QApplication
        if QtWidgets.QApplication.instance() is None:
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

        self.img_path = str(img_path)
        self.max_points = max_points
        self.points: List[Tuple[float, float]] = []  # centered coords (+y up)
        self.saved = False
        self._panning_with_space = False

        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        # ---- Main window ----
        self.win = QtWidgets.QMainWindow()
        self.win.setWindowTitle(f"Point Picker — {Path(img_path).name}")
        self.win.resize(1200, 850)
        self.win.keyPressEvent = self._on_key
        self.win.keyReleaseEvent = self._on_key_release
        self.win.closeEvent = self._on_close

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

        self.win.setCentralWidget(self.view)
        self.status = self.win.statusBar()
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
        self._point_items: List[QtWidgets.QGraphicsItem] = []

        # Fit to window initially
        self._fit_to_view()

    # ----------------- Helpers -----------------
    def _update_status(self, msg: str | None = None):
        base = "Click to add points (TL, TR, BL, BR). Backspace=undo, S=save, Q/Esc=cancel, Wheel=zoom, Space-drag=pan, F=fit, R=reset."
        if msg:
            self.status.showMessage(f"{base}  |  {msg}")
        else:
            self.status.showMessage(base)

    def _fit_to_view(self):
        self.view.fitInView(self._pix_item, self._QtCore.Qt.KeepAspectRatio)

    def _reset_zoom(self):
        # Reset transform to identity, then center
        self.view.resetTransform()
        self.view.centerOn(self._pix_item)

    def _view_to_image_xy(self, view_pos) -> Tuple[float, float]:
        """Map a QMouseEvent position to image pixel coords (top-left origin)."""
        scene_pt = self.view.mapToScene(view_pos)
        x = float(scene_pt.x())
        y = float(scene_pt.y())
        return x, y

    def _image_to_centered(self, x_tl: float, y_tl: float) -> Tuple[float, float]:
        """Convert TL-origin image coords to centered coords (+y up)."""
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
        for i, (cx, cy) in enumerate(self.points):
            x, y = self._centered_to_image(cx, cy)
            # small circle
            r = 5
            pen = QtGui.QPen(QtGui.QColor(0, 0, 0))
            brush = QtGui.QBrush(QtGui.QColor(255, 255, 255, 150))
            circ = self.scene.addEllipse(x - r, y - r, 2*r, 2*r, pen, brush)
            circ.setZValue(10)
            self._point_items.append(circ)
            # label
            lab = self.scene.addSimpleText(f"P{i} ({cx:.1f},{cy:.1f})")
            lab.setPos(x + 8, y - 8)
            lab.setZValue(11)
            self._point_items.append(lab)

    # ----------------- Events ------------------
    def _on_wheel(self, event):
        # Zoom factor
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else 0
        if delta == 0 and hasattr(event, "pixelDelta"):
            delta = event.pixelDelta().y()
        if delta == 0:
            return  # no-op fallback
        zoom_in = delta > 0
        factor = 1.15 if zoom_in else (1/1.15)
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
            # ensure inside image
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
            self.app.quit()
        elif k in (QtCore.Qt.Key_Q, QtCore.Qt.Key_Escape):
            self.points.clear()
            self.saved = False
            self.app.quit()
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

    def _on_close(self, event):
        # Auto-save only if exactly max_points were placed
        if len(self.points) == self.max_points:
            self.saved = True
        else:
            self.saved = False
        event.accept()

    def run(self) -> List[Tuple[float, float]]:
        self.win.show()
        app_exec = getattr(self.app, "exec", None) or getattr(self.app, "exec_", None)
        app_exec()
        return list(self.points) if self.saved else []


def pick_points_gui(image_file: str, max_points: int = 4) -> List[Tuple[float, float]]:
    """
    Open a GUI to pick points on an image. Returns a list of (x,y) in centered
    pixel coordinates (+y up). Returns [] if user cancels.
    """
    picker = _ImagePickerWidget(image_file, max_points=max_points)
    return picker.run()


# --------------------------------------------------
# Part 2: Solve affine / projective px->um mapping
# --------------------------------------------------
def solve_affine_px_to_um(pxs: Sequence[Tuple[float, float]],
                          ums: Sequence[Tuple[float, float]]) -> np.ndarray:
    """
    Solve 2D affine transform mapping px -> um using least squares (>=3 points).
    Returns 3x3 matrix H such that [X,Y,1]^T ~ H @ [x,y,1]^T.
    """
    if len(pxs) != len(ums) or len(pxs) < 3:
        raise ValueError("Affine fit needs >=3 correspondences and equal lengths.")
    A = []
    b = []
    for (x, y), (X, Y) in zip(pxs, ums):
        A.append([x, y, 1, 0, 0, 0])
        A.append([0, 0, 0, x, y, 1])
        b.append(X); b.append(Y)
    A = np.asarray(A, float)
    b = np.asarray(b, float)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    a, b_, c, d, e, f = sol
    H = np.array([[a, b_, c],
                  [d, e, f],
                  [0, 0, 1]], float)
    return H


def solve_proj_px_to_um(pxs: Sequence[Tuple[float, float]],
                        ums: Sequence[Tuple[float, float]]) -> np.ndarray:
    """
    Solve 2D homography (DLT) mapping px -> um. Needs exactly 4 non-degenerate correspondences.
    Returns 3x3 matrix H.
    """
    if len(pxs) != len(ums) or len(pxs) != 4:
        raise ValueError("Projective fit needs exactly 4 correspondences.")
    A = []
    for (x, y), (X, Y) in zip(pxs, ums):
        A.append([x, y, 1, 0, 0, 0, -X*x, -X*y, -X])
        A.append([0, 0, 0, x, y, 1, -Y*x, -Y*y, -Y])
    A = np.asarray(A, float)
    # Solve Ah = 0 with SVD
    U, S, Vt = np.linalg.svd(A)
    h = Vt[-1, :]
    H = h.reshape(3, 3)
    # Normalize so H[2,2] = 1 if possible
    if abs(H[2, 2]) > 1e-12:
        H = H / H[2, 2]
    return H


def build_H_px_to_um(pxs, ums, affine_only: bool) -> np.ndarray:
    return solve_affine_px_to_um(pxs, ums) if affine_only else solve_proj_px_to_um(pxs, ums)


def map_px_to_um(H: np.ndarray, x: float, y: float) -> Tuple[float, float]:
    X, Y, W = H @ np.array([x, y, 1.0], float)
    return (X / W, Y / W)


def rms_um(H: np.ndarray, pxs, ums) -> float:
    s = 0.0
    for (x, y), (Xg, Yg) in zip(pxs, ums):
        Xp, Yp = map_px_to_um(H, x, y)
        s += (Xp - Xg) ** 2 + (Yp - Yg) ** 2
    return math.sqrt(s / max(1, len(ums)))


# --------------------------------------------------
# Part 3: Optional KLayout .lys update (stub/plug-in)
# --------------------------------------------------
# Global counter for z_position
_Z_COUNTER = 0

def reset_z_counter() -> None:
    """Reset the global z-position counter so each batch starts at 1."""
    global _Z_COUNTER
    _Z_COUNTER = 0

def build_klayout_img_value(H_um_from_px: np.ndarray,
                            image_file: str,
                            px_tl_tr_br_bl: Sequence[Tuple[float, float]]) -> str:
    """
    Build the <value> string for img::Object annotations in .lys sessions.

    - H_um_from_px: 3x3 homography (px_centered -> µm)
    - px_tl_tr_br_bl: [(TLx,TLy), (TRx,TRy), (BRx,BRy), (BLx,BLy)]
    - image_file: path to image
    """

    global _Z_COUNTER
    _Z_COUNTER += 1  # increment each time this is called

    H = np.asarray(H_um_from_px, dtype=float)
    assert H.shape == (3, 3), "Expected 3x3 homography"

    # Format matrix rows
    def row(i):
        return f"({H[i,0]:.12g},{H[i,1]:.12g},{H[i,2]:.12g})"
    matrix_str = f"{row(0)} {row(1)} {row(2)}"

    # Landmarks TL,TR,BR,BL
    (tlx,tly), (trx,try_), (brx,bry), (blx,bly) = px_tl_tr_br_bl
    landmarks = f"[{tlx:.12g},{tly:.12g},{trx:.12g},{try_:.12g},{brx:.12g},{bry:.12g},{blx:.12g},{bly:.12g}]"

    # Escape Windows paths if needed
    if ":" in image_file and "\\" in image_file:
        img_path = image_file.replace("\\", "\\\\")
    else:
        img_path = image_file

    # Compose annotation string
    return (
        f"color:matrix={matrix_str};"
        f"min_value=0;max_value=255;"
        f"is_visible=true;z_position={_Z_COUNTER};"
        f"brightness=0;contrast=0;gamma=1;"
        f"red_gain=1;green_gain=1;blue_gain=1;"
        f"landmarks={landmarks};"
        f"color_mapping=[0,'#000000';1,'#ffffff';];"
        f"file='{img_path}'"
    )

def update_klayout_session(lys_in: str, lys_out: str,
                           image_file: str,
                           H_um_from_px: np.ndarray,
                           px_tl_tr_br_bl: Sequence[Tuple[float, float]]) -> None:
    """
    Load a .lys file, ensure <annotations> exists, and append an 'img::Object'.
    You MUST fill in build_klayout_img_value(...) above for your environment.
    """
    import xml.etree.ElementTree as ET
    xml = Path(lys_in).read_text(encoding="utf-8")
    root = ET.fromstring(xml)

    # Find <view> node
    view = None
    for el in root.iter():
        if el.tag == "view":
            view = el
            break
    if view is None:
        raise RuntimeError("No <view> element found in LYS.")

    # Ensure annotations node
    anns = None
    for el in view:
        if el.tag == "annotations":
            anns = el
            break
    if anns is None:
        anns = ET.SubElement(view, "annotations")

    ann = ET.SubElement(anns, "annotation")
    ET.SubElement(ann, "class").text = "img::Object"
    val = ET.SubElement(ann, "value")
    val.text = build_klayout_img_value(H_um_from_px, Path(image_file).as_posix(), px_tl_tr_br_bl)

    Path(lys_out).write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")


# --------------------------------------------------
# Part 4: High-level "AlignMarkers" method
# --------------------------------------------------
@dataclass
class AlignConfig:
    after_pts_um: Sequence[Tuple[float, float]]     # TL, TR, BL, BR in µm
    affine_only: bool = True
    rms_thresh_um: float = 0.5
    after_origin_um: Tuple[float, float] = (0.0, 0.0)  # optional translational offset applied to target

from typing import List, Sequence, Tuple, Optional

def run_point_alignment(
    image_path: str,
    after_pts_um: Sequence[Tuple[float, float]],
    *,
    affine_only: bool = True,
    rms_thresh_um: float = 0.5,
    origin_um: Optional[Tuple[float, float]] = None,
    out_json: Optional[str] = None,
    lys_in: Optional[str] = None,
    lys_out: Optional[str] = None
):
    """
    Programmatic entry point: pick 4 points on an image, align to given AFTER points,
    (optionally) save clicks and (optionally) update a KLayout .lys session.

    Returns:
        (H_um_from_px, rms_um_value, picked_points_centered_px)
    """
        # 1) Acquire four points: try auto-detect first if enabled, else fall back to GUI picker.
    pts_cxcy = None
    use_auto, auto_review = _AUTO_FLAGS if "_AUTO_FLAGS" in globals() else (False, False)

    if use_auto and detect_four_points_centered is not None:
        try:
            params = _AUTO_PARAMS if "_AUTO_PARAMS" in globals() else None
            pts_cxcy = detect_four_points_centered(image_path, params=params)
            if auto_review:
                # Pre-seed your existing Qt picker so the user can nudge & press S
                picker = _ImagePickerWidget(image_path, max_points=4)  # uses your current picker:contentReference[oaicite:3]{index=3}
                picker.points = list(pts_cxcy)
                picker._redraw_points()
                pts_cxcy = picker.run()
        except Exception as e:
            print(f"[auto] detection failed: {e}", file=sys.stderr)
            pts_cxcy = None

    if not pts_cxcy:
        # Fall back to your existing picker:contentReference[oaicite:4]{index=4}
        pts_cxcy = pick_points_gui(image_path, max_points=4)

    if not pts_cxcy:
        raise RuntimeError("No points were picked (user cancelled or window closed).")

    # 2) Alignment config
    cfg = AlignConfig(
        after_pts_um=list(after_pts_um),
        affine_only=affine_only,
        rms_thresh_um=rms_thresh_um,
        after_origin_um=origin_um or (0.0, 0.0),
    )

    # 3) Compute transform
    H_um_from_px, rms = align_markers(
    pts_cxcy, cfg,
    lys_in=lys_in, lys_out=lys_out, image_file=image_path
    )
    return H_um_from_px, rms, pts_cxcy

    # 4) KLayout .lys update
def align_markers(before_ctr_px: Sequence[Tuple[float, float]],
                  cfg: AlignConfig,
                  lys_in: str | None = None,
                  lys_out: str | None = None,
                  image_file: str | None = None) -> Tuple[np.ndarray, float]:
    """
    Compute transform from centered image pixels -> microns, optionally update .lys.
    Returns (H_um_from_px, rms_um).

    - before_ctr_px: TL, TR, BL, BR *in that order*, centered px (+y up).
    - cfg.after_pts_um: same ordering in µm.
    - cfg.after_origin_um: applied as translation to all target points (optional).
    """
    if len(before_ctr_px) != 4 or len(cfg.after_pts_um) != 4:
        raise ValueError("Need 4 points for before and after (TL,TR,BL,BR).")

    # Apply optional origin shift to AFTER targets
    ox, oy = cfg.after_origin_um
    after_shifted = [(X + ox, Y + oy) for (X, Y) in cfg.after_pts_um]

    H = build_H_px_to_um(before_ctr_px, after_shifted, cfg.affine_only)
    err = rms_um(H, before_ctr_px, after_shifted)

    if err > cfg.rms_thresh_um:
        print(f"[WARN] RMS {err:.3f} µm exceeds threshold {cfg.rms_thresh_um:.3f} µm", file=sys.stderr)

    if lys_in and lys_out and image_file:
        # Order for the image corners if needed by your KLayout value string.
        # Many flows expect TL, TR, BR, BL for quads; adjust to what your build_... expects.
        px_tl_tr_br_bl = [before_ctr_px[0], before_ctr_px[1], before_ctr_px[3], before_ctr_px[2]]
        update_klayout_session(lys_in, lys_out, image_file, H, px_tl_tr_br_bl)

    return H, err


# --------------------------------------------------
# Part 5: "pick -> save" and "pick -> align" methods
# --------------------------------------------------
def save_clicks_json(out_json: str, centered_pts: Sequence[Tuple[float, float]]) -> None:
    Path(out_json).write_text(json.dumps({"centered_px": list(map(list, centered_pts))}, indent=2), encoding="utf-8")


def load_clicks_json(in_json: str) -> List[Tuple[float, float]]:
    data = json.loads(Path(in_json).read_text(encoding="utf-8"))
    pts = data.get("centered_px")
    if not isinstance(pts, list) or not all(isinstance(p, list) and len(p) == 2 for p in pts):
        raise ValueError("JSON missing 'centered_px': [[x,y], ...]")
    return [(float(p[0]), float(p[1])) for p in pts]


def run_combo(image_file: str,
              cfg: AlignConfig,
              out_json: str | None = None,
              lys_in: str | None = None,
              lys_out: str | None = None) -> Tuple[np.ndarray, float]:
    """
    Opens the picker; if user saves 4 points, immediately runs align_markers.
    Optionally writes the clicks to out_json.
    """
    pts = pick_points_gui(image_file, max_points=4)
    if not pts:
        raise RuntimeError("No points saved (user canceled).")
    if out_json:
        save_clicks_json(out_json, pts)
    H, err = align_markers(pts, cfg, lys_in=lys_in, lys_out=lys_out, image_file=image_file)
    return H, err


# ------------------------------
# Part 6: Command-line interface
# ------------------------------
def _cli():
    p = argparse.ArgumentParser(description="Point picking + alignment (single-file tool)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # pick
    pp = sub.add_parser("pick", help="Open GUI to pick 4 points and save to JSON")
    pp.add_argument("--image", required=True, help="Path to image file")
    pp.add_argument("--out", default="clicks.json", help="Output JSON path (default: clicks.json)")

    # align
    al = sub.add_parser("align", help="Compute transform from saved clicks or inline points")
    al.add_argument("--clicks", help="clicks.json produced by 'pick'")
    al.add_argument("--before", help="Inline points: '(-731,523),(320,499),(-752,-530),(298,-550)'")
    al.add_argument("--after", required=True, type=parse_pts, help="Target µm points TL,TR,BL,BR")
    al.add_argument("--affine-only", action="store_true", help="Use affine (>=3 points) instead of projective (4 points)")
    al.add_argument("--rms-thresh", type=float, default=0.5, help="Warn if RMS exceeds this (µm)")
    al.add_argument("--origin", type=parse_pts, help="Optional single (ox,oy) shift applied to AFTER points")
    al.add_argument("--lys-in", help="(Optional) Input .lys to update with image annotation")
    al.add_argument("--lys-out", help="(Optional) Output .lys file to write")
    al.add_argument("--image-file", help="(Optional) Image file path for KLayout annotation")

    # run
    rn = sub.add_parser("run", help="Pick points then align immediately")
    rn.add_argument("--image", required=True, help="Path to image file")
    rn.add_argument("--after", required=True, type=parse_pts, help="Target µm points TL,TR,BL,BR")
    rn.add_argument("--affine-only", action="store_true", help="Use affine instead of projective")
    rn.add_argument("--rms-thresh", type=float, default=0.5, help="Warn if RMS exceeds this (µm)")
    rn.add_argument("--origin", type=parse_pts, help="Optional single (ox,oy) shift applied to AFTER points")
    rn.add_argument("--out", default="clicks.json", help="Also save picked points here")
    rn.add_argument("--lys-in", help="(Optional) Input .lys to update")
    rn.add_argument("--lys-out", help="(Optional) Output .lys file")
    # (image used in KL update reuses --image)

    args = p.parse_args()

    if args.cmd == "pick":
        pts = pick_points_gui(args.image, max_points=4)
        if not pts:
            print("No points saved.", file=sys.stderr)
            sys.exit(2)
        save_clicks_json(args.out, pts)
        print(f"Wrote {args.out}")
        for i, (x, y) in enumerate(pts):
            print(f"  P{i}: ({x:.3f}, {y:.3f}) px (centered)")

    elif args.cmd == "align":
        if not args.clicks and not args.before:
            print("Provide --clicks or --before", file=sys.stderr)
            sys.exit(2)
        if args.clicks:
            before = load_clicks_json(args.clicks)
        else:
            before = parse_pts(args.before)

        origin = (0.0, 0.0)
        if args.origin:
            if len(args.origin) != 1:
                print("--origin expects exactly one pair like '(ox,oy)'", file=sys.stderr)
                sys.exit(2)
            origin = args.origin[0]

        cfg = AlignConfig(after_pts_um=args.after,
                          affine_only=args.affine_only,
                          rms_thresh_um=args.rms_thresh,
                          after_origin_um=origin)

        H, err = align_markers(before, cfg,
                               lys_in=args.lys_in,
                               lys_out=args.lys_out,
                               image_file=args.image_file)
        print("H (µm from px):")
        np.set_printoptions(precision=6, suppress=True)
        print(H)
        print(f"RMS error: {err:.6f} µm")

    elif args.cmd == "run":
        origin = (0.0, 0.0)
        if args.origin:
            if len(args.origin) != 1:
                print("--origin expects exactly one pair like '(ox,oy)'", file=sys.stderr)
                sys.exit(2)
            origin = args.origin[0]
        cfg = AlignConfig(after_pts_um=args.after,
                          affine_only=args.affine_only,
                          rms_thresh_um=args.rms_thresh,
                          after_origin_um=origin)
        H, err = run_combo(args.image, cfg, out_json=args.out,
                           lys_in=args.lys_in, lys_out=args.lys_out)
        print("H (µm from px):")
        np.set_printoptions(precision=6, suppress=True)
        print(H)
        print(f"RMS error: {err:.6f} µm")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Point-pick and align (callable + CLI).")
    sub = p.add_subparsers(dest="cmd", required=True)

    # pick
    pp = sub.add_parser("pick", help="Open GUI to pick 4 points and save to JSON")
    pp.add_argument("--image", required=True, help="Path to image file")
    pp.add_argument("--out", default="clicks.json", help="Output JSON path (default: clicks.json)")

    # align
    al = sub.add_parser("align", help="Compute transform from saved clicks or inline points")
    al.add_argument("--clicks", help="clicks.json produced by 'pick'")
    al.add_argument("--before", help="Inline points: '(-731,523),(320,499),(-752,-530),(298,-550)'")
    al.add_argument("--after", required=True, type=parse_pts, help="Target µm points TL,TR,BL,BR")
    al.add_argument("--affine-only", action="store_true", help="Use affine (>=3 points) instead of projective (4 points)")
    al.add_argument("--rms-thresh", type=float, default=0.5, help="Warn if RMS exceeds this (µm)")
    al.add_argument("--origin", type=parse_pts, help="Optional single (ox,oy) shift applied to AFTER points")
    al.add_argument("--lys-in", help="(Optional) Input .lys to update with image annotation")
    al.add_argument("--lys-out", help="(Optional) Output .lys file to write")
    al.add_argument("--image-file", help="(Optional) Image file path for KLayout annotation")

    # run (pick then align; now a thin wrapper over run_point_alignment)
    rn = sub.add_parser("run", help="Pick points then align immediately (programmatic wrapper)")
    rn.add_argument("--image", required=True, help="Path to image file")
    rn.add_argument("--after", required=True, type=parse_pts, help="Target µm points TL,TR,BL,BR")
    rn.add_argument("--affine-only", action="store_true", help="Use affine instead of projective")
    rn.add_argument("--rms-thresh", type=float, default=0.5, help="Warn if RMS exceeds this (µm)")
    rn.add_argument("--origin", type=parse_pts, help="Optional single (ox,oy) shift applied to AFTER points")
    rn.add_argument("--out", default="clicks.json", help="Also save picked points here")
    rn.add_argument("--lys-in", help="(Optional) Input .lys to update")
    rn.add_argument("--lys-out", help="(Optional) Output .lys file")

    args = p.parse_args()

    try:
        if args.cmd == "pick":
            pts = pick_points_gui(args.image, max_points=4)
            if not pts:
                print("No points saved.", file=sys.stderr)
                sys.exit(2)
            save_clicks_json(args.out, pts)
            print(f"Wrote {args.out}")
            for i, (x, y) in enumerate(pts):
                print(f"  P{i}: ({x:.3f}, {y:.3f}) px (centered)")

        elif args.cmd == "align":
            if not args.clicks and not args.before:
                print("Provide --clicks or --before", file=sys.stderr)
                sys.exit(2)
            if args.clicks:
                before = load_clicks_json(args.clicks)
            else:
                before = parse_pts(args.before)

            origin = None
            if args.origin:
                if len(args.origin) != 1:
                    print("--origin must be a single (ox,oy) tuple", file=sys.stderr)
                    sys.exit(2)
                origin = args.origin[0]

            cfg = AlignConfig(
                after_pts_um=args.after,
                affine_only=args.affine_only,
                rms_thresh_um=args.rms_thresh,
                after_origin_um=origin or (0.0, 0.0),
            )

            H_um, rms = align_markers(before, cfg)
            print("H (px→µm):")
            np.set_printoptions(precision=6, suppress=True)
            print(H_um)
            print(f"RMS = {rms:.6f} µm")

            # Optional KLayout update (requires project-specific value builder)
            if args.lys_in and args.lys_out and args.image_file:
                update_klayout_session(
                    lys_in=args.lys_in,
                    lys_out=args.lys_out,
                    image_file=args.image_file,
                    H_um_from_px=H_um,
                    px_tl_tr_br_bl=before,
                )
                print(f"Updated {args.lys_out}")

        elif args.cmd == "run":
            origin = None
            if args.origin:
                if len(args.origin) != 1:
                    print("--origin must be a single (ox,oy) tuple", file=sys.stderr)
                    sys.exit(2)
                origin = args.origin[0]

            H_um, rms, pts = run_point_alignment(
                image_path=args.image,
                after_pts_um=args.after,
                affine_only=args.affine_only,
                rms_thresh_um=args.rms_thresh,
                origin_um=origin,
                out_json=args.out,
                lys_in=args.lys_in,
                lys_out=args.lys_out,
            )

            np.set_printoptions(precision=6, suppress=True)
            print("H (px→µm):")
            print(H_um)
            print(f"RMS = {rms:.6f} µm")
            print(f"Saved clicks to {args.out}")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
        
