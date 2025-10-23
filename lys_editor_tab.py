
# lys_editor_tab.py
# Updated: detects KLayout img::Object entries AND supports double-click image preview
# with optional application of the saved 3×3 transform from the .lys file.
#
# The .lys 'value' field contains:
#   color:matrix=(a,b,c) (d,e,f) (g,h,i); ... file='...'
# Here, matrix maps centered pixel coords (+y up) to microns. We compose:
#   M = H_um_from_px @ A
# where A converts top-left pixel coords (Qt image space) to centered coords:
#   A = [[1, 0, -w/2],
#        [0,-1,  h/2],
#        [0, 0,    1]]
#
from __future__ import annotations
import os, re
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple, Dict

from PySide6 import QtCore, QtGui, QtWidgets

IMG_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}

def _is_image_path(s: str) -> bool:
    try:
        return Path(s).suffix.lower() in IMG_EXTS
    except Exception:
        return False

def _parse_matrix_from_value(txt: str) -> Optional[Tuple[Tuple[float,float,float],Tuple[float,float,float],Tuple[float,float,float]]]:
    """
    Extract 3 rows of the 'matrix=(r0)(r1)(r2)' from a value string.
    Rows are of the form '(a,b,c)'
    Returns a 3x3 tuple-of-tuples or None.
    """
    if not isinstance(txt, str):
        return None
    m = re.search(r"matrix\s*=\s*\(([^)]+)\)\s*\(([^)]+)\)\s*\(([^)]+)\)", txt)
    if not m:
        return None
    rows = []
    for i in range(1, 4):
        parts = [p.strip() for p in m.group(i).split(",")]
        if len(parts) != 3:
            return None
        try:
            rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
        except Exception:
            return None
    return (rows[0], rows[1], rows[2])

class _ListItem(QtWidgets.QListWidgetItem):
    def __init__(self, display: str, elem_id: int):
        super().__init__(display)
        self.setData(QtCore.Qt.ItemDataRole.UserRole, elem_id)

class ImagePreviewDialog(QtWidgets.QDialog):
    """Zoomable image preview with optional transform application."""
    def __init__(self, img_path: str, H_um_from_px: Optional[Tuple[Tuple[float,float,float],Tuple[float,float,float],Tuple[float,float,float]]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Preview — {Path(img_path).name}")
        self.resize(1100, 780)
        self._H = H_um_from_px
        self._img_path = img_path

        v = QtWidgets.QVBoxLayout(self)

        # Scene/View
        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.view.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        v.addWidget(self.view, 1)

        # Toolbar
        bar = QtWidgets.QHBoxLayout()
        self.chk_transform = QtWidgets.QCheckBox("Apply saved transform")
        self.chk_transform.setChecked(self._H is not None)
        self.btn_fit = QtWidgets.QPushButton("Fit")
        self.btn_reset = QtWidgets.QPushButton("100%")
        self.lbl_info = QtWidgets.QLabel("")
        self.lbl_info.setStyleSheet("color:#666;")
        bar.addWidget(self.chk_transform)
        bar.addSpacing(8)
        bar.addWidget(self.btn_fit)
        bar.addWidget(self.btn_reset)
        bar.addStretch(1)
        bar.addWidget(self.lbl_info)
        v.addLayout(bar)

        # Load image
        qimg = QtGui.QImage(img_path)
        if qimg.isNull():
            raise RuntimeError(f"Could not load image:\n{img_path}")
        self._img_w = qimg.width()
        self._img_h = qimg.height()
        self._pix = QtGui.QPixmap.fromImage(qimg)

        self._pix_item = QtWidgets.QGraphicsPixmapItem(self._pix)
        self._pix_item.setZValue(0)
        self.scene.addItem(self._pix_item)

        # Simple axes/scale overlay (micron grid when transform applied)
        self._grid_items: list = []

        # Events
        self._ZOOM_STEP = 1.25
        self.view.wheelEvent = self._on_wheel
        self.btn_fit.clicked.connect(self._fit)
        self.btn_reset.clicked.connect(self._reset)
        self.chk_transform.toggled.connect(self._apply_current_transform)

        self._update_info()
        self._apply_current_transform()
        self._fit()

    def _update_info
        mode = "Transformed (µm)" if (self.chk_transform.isChecked() and self._H) else "Raw pixels"
        self.lbl_info.setText(f"{self._img_w}×{self._img_h}px  —  {mode}.  Wheel: zoom, Drag: pan")

    def _fit
        self.view.fitInView(self._pix_item, QtCore.Qt.KeepAspectRatio)

    def _reset
        self.view.resetTransform()
        self.view.centerOn(self._pix_item)

    def _on_wheel(self, event):
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else 0
        if delta == 0 and hasattr(event, "pixelDelta"):
            delta = event.pixelDelta().y()
        if delta == 0:
            return
        zoom_in = delta > 0
        factor = self._ZOOM_STEP if zoom_in else (1.0 / self._ZOOM_STEP)
        self.view.scale(factor, factor)

    def _clear_grid
        for it in self._grid_items:
            self.scene.removeItem(it)
        self._grid_items.clear()

    def _draw_micron_grid(self, spacing_um: float = 50.0, lines: int = 10):
        """Draw a faint crosshair/grid around origin in micron space (only when transformed)."""
        # Use QtGui directly; do NOT grab types off QPalette (bug fix)
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 80))
        pen.setWidthF(0)
        pen2 = QtGui.QPen(QtGui.QColor(0, 0, 255, 110))
        pen2.setWidthF(0)

        # Crosshair
        l1 = self.scene.addLine(-lines*spacing_um, 0, lines*spacing_um, 0, pen2)
        l2 = self.scene.addLine(0, -lines*spacing_um, 0, lines*spacing_um, pen2)
        self._grid_items.extend([l1, l2])

        # Grid
        for i in range(-lines, lines+1):
            if i == 0:
                continue
            x = i * spacing_um
            self._grid_items.append(self.scene.addLine(x, -lines*spacing_um, x, lines*spacing_um, pen))
            y = i * spacing_um
            self._grid_items.append(self.scene.addLine(-lines*spacing_um, y, lines*spacing_um, y, pen))

    def _apply_current_transform

        self._clear_grid()
        if self.chk_transform.isChecked() and self._H is not None:
            # Compose M = H @ A
            a11, a12, a13 = 1.0, 0.0, -self._img_w / 2.0
            a21, a22, a23 = 0.0,-1.0,  self._img_h / 2.0
            a31, a32, a33 = 0.0, 0.0, 1.0

            H = self._H
            # Matrix multiplication M = H @ A
            def mult3(H, A):
                return (
                    (
                        H[0][0]*A[0][0] + H[0][1]*A[1][0] + H[0][2]*A[2][0],
                        H[0][0]*A[0][1] + H[0][1]*A[1][1] + H[0][2]*A[2][1],
                        H[0][0]*A[0][2] + H[0][1]*A[1][2] + H[0][2]*A[2][2],
                    ),
                    (
                        H[1][0]*A[0][0] + H[1][1]*A[1][0] + H[1][2]*A[2][0],
                        H[1][0]*A[0][1] + H[1][1]*A[1][1] + H[1][2]*A[2][1],
                        H[1][0]*A[0][2] + H[1][1]*A[1][2] + H[1][2]*A[2][2],
                    ),
                    (
                        H[2][0]*A[0][0] + H[2][1]*A[1][0] + H[2][2]*A[2][0],
                        H[2][0]*A[0][1] + H[2][1]*A[1][1] + H[2][2]*A[2][1],
                        H[2][0]*A[0][2] + H[2][1]*A[1][2] + H[2][2]*A[2][2],
                    ),
                )
            A = ((a11,a12,a13),(a21,a22,a23),(a31,a32,a33))
            M = mult3(H, A)

            qM = QtGui.QTransform(
                M[0][0], M[0][1], M[0][2],
                M[1][0], M[1][1], M[1][2],
                M[2][0], M[2][1], M[2][2],
            )
            self._pix_item.setTransform(qM, combine=False)
            self._draw_micron_grid()
        else:
            self._pix_item.setTransform(QtGui.QTransform())
        self._update_info()
        self._fit()

class LYSTab(QtWidgets.QWidget):
    fileLoaded = QtCore.Signal(str)
    fileSaved = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("LYSEditorTab")

        # XML state
        self._current_path: Optional[Path] = None
        self._tree: Optional[ET.ElementTree] = None
        self._root: Optional[ET.Element] = None
        self._elem_seq = 0
        self._id_to_elem: Dict[int, ET.Element] = {}
        self._ordered_parent: Optional[ET.Element] = None

        self._build_ui()
        self._wire_logic()
        self._update_buttons_enabled()

    # ---------------- UI ----------------
    def _build_ui
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        grp_open = QtWidgets.QGroupBox("Open .LYS file")
        v.addWidget(grp_open)
        h = QtWidgets.QHBoxLayout(grp_open)
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("Select a KLayout .lys session file…")
        self.btn_browse = QtWidgets.QPushButton("Browse…")
        self.btn_reload = QtWidgets.QPushButton("Reload")
        self.btn_reload.setToolTip("Reload the file from disk")
        h.addWidget(QtWidgets.QLabel("Session file:"))
        h.addWidget(self.path_edit, 1)
        h.addWidget(self.btn_browse)
        h.addWidget(self.btn_reload)

        body = QtWidgets.QWidget()
        v.addWidget(body, 1)
        grid = QtWidgets.QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.list.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.list.setAlternatingRowColors(True)
        self.list.setUniformItemSizes(True)

        btns = QtWidgets.QVBoxLayout()
        self.btn_up = QtWidgets.QPushButton("Up")
        self.btn_down = QtWidgets.QPushButton("Down")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        for b in (self.btn_up, self.btn_down, self.btn_delete):
            b.setAutoDefault(False)
        btns.addWidget(self.btn_up)
        btns.addWidget(self.btn_down)
        btns.addSpacing(8)
        btns.addWidget(self.btn_delete)
        btns.addStretch(1)

        grid.addWidget(QtWidgets.QLabel("Images / annotations (drag to reorder, double-click to preview):"), 0, 0, 1, 2)
        grid.addWidget(self.list, 1, 0, 1, 1)
        grid.addLayout(btns, 1, 1, 1, 1)

        save_bar = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save")
        self.btn_save_as = QtWidgets.QPushButton("Save As…")
        self.lbl_status = QtWidgets.QLabel("")
        self.lbl_status.setStyleSheet("color:#555;")
        save_bar.addWidget(self.btn_save)
        save_bar.addWidget(self.btn_save_as)
        save_bar.addStretch(1)
        save_bar.addWidget(self.lbl_status)
        v.addLayout(save_bar)

        self.btn_delete.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Delete))
        self.btn_save.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        self.btn_save_as.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.btn_up.setShortcut(QtGui.QKeySequence("Alt+Up"))
        self.btn_down.setShortcut(QtGui.QKeySequence("Alt+Down"))

    def _wire_logic
        self.btn_browse.clicked.connect(self._browse)
        self.btn_reload.clicked.connect(self.reload)
        self.btn_up.clicked.connect(self._move_up_clicked)
        self.btn_down.clicked.connect(self._move_down_clicked)
        self.btn_delete.clicked.connect(self._delete_clicked)
        self.btn_save.clicked.connect(self.save)
        self.btn_save_as.clicked.connect(self.save_as)
        self.list.model().rowsMoved.connect(self._list_reordered)
        self.list.itemSelectionChanged.connect(self._update_buttons_enabled)
        self.path_edit.returnPressed.connect(self.reload)
        self.list.itemDoubleClicked.connect(self._preview_item)

    # -------- File loading / parsing --------
    def _update_buttons_enabled
        has_items = self.list.count() > 0
        any_selected = len(self.list.selectedIndexes()) > 0
        self.btn_up.setEnabled(any_selected and has_items)
        self.btn_down.setEnabled(any_selected and has_items)
        self.btn_delete.setEnabled(any_selected and has_items)
        self.btn_save.setEnabled(has_items and self._tree is not None and self._ordered_parent is not None)
        self.btn_save_as.setEnabled(has_items and self._tree is not None and self._ordered_parent is not None)
        self.btn_reload.setEnabled(self._current_path is not None and self._current_path.exists())

    def _browse
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select a .LYS file", "", "KLayout Session (*.lys);;All files (*.*)"
        )
        if path:
            self.path_edit.setText(path)
            self.load(Path(path))

    def reload
        p = self.path_edit.text().strip()
        if p:
            self.load(Path(p))

    def _status(self, text: str):
        self.lbl_status.setText(text)

    # ---- Image path & transform helpers ----
    def _extract_img_file(self, elem: ET.Element) -> Optional[str]:
        """Extract image path from <annotation><class>img::Object</class><value>file='...'</value>"""
        if elem.tag != "annotation":
            return None
        cls = elem.find("class")
        if cls is None or (cls.text or "").strip().lower() != "img::object":
            return None
        val = elem.find("value")
        if val is None or not isinstance(val.text, str):
            return None
        m = re.search(r"file\s*=\s*['\"]([^'\"]+)['\"]", val.text)
        return m.group(1) if m else None

    def _extract_img_matrix(self, elem: ET.Element):
        """Return 3×3 tuple matrix from the <value> string, or None."""
        if elem.tag != "annotation":
            return None
        cls = elem.find("class")
        if cls is None or (cls.text or "").strip().lower() != "img::object":
            return None
        val = elem.find("value")
        if val is None or not isinstance(val.text, str):
            return None
        return _parse_matrix_from_value(val.text)

    def _resolve_img_path(self, f: str) -> Optional[str]:
        """Try to resolve path as-is, normalize, and relative to the .lys folder."""
        if not f:
            return None
        cands = [Path(f)]
        cands.append(Path(f.replace("\\\\", "\\")))
        cands.append(Path(f.replace("\\", "/")))
        if self._current_path:
            base = self._current_path.parent
            for c in list(cands):
                if not c.is_absolute():
                    cands.append(base / c)
        for c in cands:
            try:
                if c.exists() and c.is_file():
                    return str(c)
            except Exception:
                pass
        return None

    def _element_is_image_like(self, elem: ET.Element) -> bool:
        f = self._extract_img_file(elem)
        if f and _is_image_path(f):
            return True
        for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href"):
            v = elem.attrib.get(key)
            if v and _is_image_path(v):
                return True
        for v in elem.attrib.values():
            if isinstance(v, str) and _is_image_path(v):
                return True
        name = elem.attrib.get("name") or elem.attrib.get("object-name") or ""
        if "img::" in name.lower():
            return True
        for child in list(elem):
            for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href", "value"):
                v = child.attrib.get(key)
                if v and _is_image_path(v):
                    return True
            if child.tag == "value" and isinstance(child.text, str):
                m = re.search(r"file\s*=\s*['\"]([^'\"]+)['\"]", child.text)
                if m and _is_image_path(m.group(1)):
                    return True
        return False

    def _describe_elem(self, elem: ET.Element) -> str:
        f = self._extract_img_file(elem)
        if f:
            try:
                return Path(f).name or f
            except Exception:
                return f
        candidates = []
        for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href"):
            v = elem.attrib.get(key)
            if v:
                candidates.append(v)
        for key in ("name", "object-name", "label", "type"):
            v = elem.attrib.get(key)
            if v:
                candidates.append(v)
        for child in list(elem):
            for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href", "value"):
                v = child.attrib.get(key)
                if v:
                    candidates.append(v)
            if child.tag == "value" and isinstance(child.text, str):
                m = re.search(r"file\s*=\s*['\"]([^'\"]+)['\"]", child.text)
                if m:
                    candidates.append(m.group(1))
        if candidates:
            try:
                pn = Path(candidates[0])
                if pn.suffix and pn.name:
                    return pn.name
            except Exception:
                pass
            return candidates[0]
        attrs = " ".join(f'{k}="{v}"' for k, v in list(elem.attrib.items())[:2])
        return f"<{elem.tag} {attrs}>".strip()

    def _parent_of(self, elem: ET.Element) -> Optional[ET.Element]:
        if self._root is None:
            return None
        for parent in self._root.iter():
            for child in list(parent):
                if child is elem:
                    return parent
        return None

    def load(self, path: Path):
        try:
            path = path.resolve()
        except Exception:
            pass
        if not path.exists():
            QtWidgets.QMessageBox.critical(self, "File not found", f"Path does not exist:\n{path}")
            return
        try:
            tree = ET.parse(str(path))
            root = tree.getroot()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Parse error", f"Failed to parse XML:\n{e}")
            return

        self._current_path = path
        self._tree = tree
        self._root = root
        self._id_to_elem.clear()
        self._elem_seq = 0
        self._ordered_parent = None
        self.list.clear()

        elems, parent = self._find_image_like_elems(root)
        if not elems:
            self._status("No image-like annotations found.")
            self._update_buttons_enabled()
            self.fileLoaded.emit(str(path))
            return

        self._ordered_parent = parent
        for elem in elems:
            self._elem_seq += 1
            elem_id = self._elem_seq
            self._id_to_elem[elem_id] = elem
            label = self._describe_elem(elem)
            self.list.addItem(_ListItem(label, elem_id))

        self._status(f"Loaded {len(elems)} items from {path.name}")
        self.fileLoaded.emit(str(path))
        self._update_buttons_enabled()

    def _find_image_like_elems(self, root: ET.Element) -> Tuple[List[ET.Element], Optional[ET.Element]]:
        annotations = root.find(".//annotations")
        if annotations is not None:
            hits = [e for e in list(annotations) if self._element_is_image_like(e)]
            if hits:
                return hits, annotations
        parent_to_hits: Dict[ET.Element, List[ET.Element]] = {}
        for e in root.iter():
            if self._element_is_image_like(e):
                parent = self._parent_of(e)
                if parent is not None:
                    parent_to_hits.setdefault(parent, []).append(e)
        if parent_to_hits:
            best_parent = max(parent_to_hits.items(), key=lambda kv: len(kv[1]))[0]
            return parent_to_hits[best_parent], best_parent
        return [], None

    # -------- Preview --------
    def _item_elem_id(self, item: QtWidgets.QListWidgetItem) -> int:
        return int(item.data(QtCore.Qt.ItemDataRole.UserRole))

    def _preview_item(self, item: QtWidgets.QListWidgetItem):
        elem_id = self._item_elem_id(item)
        elem = self._id_to_elem.get(elem_id)
        if not elem:
            return
        raw = self._extract_img_file(elem)
        if not raw:
            QtWidgets.QMessageBox.information(self, "No image", "This annotation has no image path.")
            return
        resolved = self._resolve_img_path(raw)
        if not resolved:
            msg = f"Could not find image on disk:\n{raw}"
            if self._current_path:
                msg += f"\n(Tried relative to: {self._current_path.parent})"
            QtWidgets.QMessageBox.warning(self, "File not found", msg)
            return
        H = self._extract_img_matrix(elem)
        try:
            dlg = ImagePreviewDialog(resolved, H_um_from_px=H, parent=self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Preview failed", str(e))

    # -------- Editing actions --------
    def _selected_rows(self) -> List[int]:
        return sorted({idx.row() for idx in self.list.selectedIndexes()})

    def _move_up_clicked
        rows = self._selected_rows()
        if not rows:
            return
        for r in rows:
            if r > 0:
                self._swap_rows(r, r - 1)
        self._restore_selection([r - (1 if r > 0 else 0) for r in rows])
        self._list_reordered()

    def _move_down_clicked
        rows = sorted(self._selected_rows(), reverse=True)
        if not rows:
            return
        for r in rows:
            if r < self.list.count() - 1:
                self._swap_rows(r, r + 1)
        self._restore_selection([r + (1 if r < self.list.count() - 1 else 0) for r in rows])
        self._list_reordered()

    def _swap_rows(self, i: int, j: int):
        if i == j:
            return
        item_i = self.list.takeItem(i)
        item_j = self.list.takeItem(j - 1 if j > i else j)
        if item_j is not None:
            self.list.insertItem(i, item_j)
        if item_i is not None:
            self.list.insertItem(j, item_i)

    def _restore_selection(self, rows: List[int]):
        self.list.clearSelection()
        for r in rows:
            if 0 <= r < self.list.count():
                self.list.item(r).setSelected(True)

    def _delete_clicked
        rows = self._selected_rows()
        if not rows:
            return
        resp = QtWidgets.QMessageBox.question(
            self,
            "Delete entries",
            f"Delete {len(rows)} selected item(s) from this session?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        if resp != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        for r in reversed(rows):
            self.list.takeItem(r)
        if self._ordered_parent is not None and self._tree is not None:
            keep_ids = [self._item_elem_id(self.list.item(i)) for i in range(self.list.count())]
            keep_elems = [self._id_to_elem[i] for i in keep_ids if i in self._id_to_elem]
            for child in list(self._ordered_parent):
                self._ordered_parent.remove(child)
            for e in keep_elems:
                self._ordered_parent.append(e)
            keep_set = set(keep_ids)
            self._id_to_elem = {i: self._id_to_elem[i] for i in keep_set if i in self._id_to_elem}
        self._status("Deleted. (Remember to Save) ")
        self._update_buttons_enabled()

    def _list_reordered(self, *args):
        if self._ordered_parent is None or self._tree is None:
            return
        ids_in_order = [self._item_elem_id(self.list.item(i)) for i in range(self.list.count())]
        elems = [self._id_to_elem[i] for i in ids_in_order if i in self._id_to_elem]
        for child in list(self._ordered_parent):
            self._ordered_parent.remove(child)
        for e in elems:
            self._ordered_parent.append(e)
        self._status("Reordered. (Remember to Save) ")
        self._update_buttons_enabled()

    # -------- Saving --------
    def _ensure_backup(self, path: Path):
        try:
            if path.exists():
                bak = path.with_suffix(path.suffix + ".bak")
                if (not bak.exists()) or (bak.stat().st_size != path.stat().st_size):
                    bak.write_bytes(path.read_bytes())
        except Exception:
            pass

    def save
        if self._tree is None or self._current_path is None:
            return
        self._ensure_backup(self._current_path)
        try:
            self._tree.write(self._current_path, encoding="utf-8", xml_declaration=True)
            self._status(f"Saved: {self._current_path.name}")
            self.fileSaved.emit(str(self._current_path))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))

    def save_as
        if self._tree is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save .LYS as…", "", "KLayout Session (*.lys);;All files (*.*)"
        )
        if not path:
            return
        dest = Path(path)
        try:
            self._tree.write(dest, encoding="utf-8", xml_declaration=True)
            self._status(f"Saved as: {dest.name}")
            self.fileSaved.emit(str(dest))
            self._current_path = dest
            self.path_edit.setText(str(dest))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))


class _Window(QtWidgets.QMainWindow):
    def __init__
        super().__init__()
        self.setWindowTitle(".LYS Editor — Standalone")
        self.resize(900, 600)
        tab = LYSTab(self)
        self.setCentralWidget(tab)


def _main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = _Window()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _main()
