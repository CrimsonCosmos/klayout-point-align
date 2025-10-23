# lys_editor_tab.py — Side-by-side .LYS tab (copy between files), raw preview only
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import re
import xml.etree.ElementTree as ET
from copy import deepcopy

from PySide6 import QtCore, QtGui, QtWidgets

IMG_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}


# ---------------- helpers ----------------
def _parse_value_for_file_and_matrix(text: str) -> Tuple[Optional[str], Optional[Tuple[Tuple[float,float,float],Tuple[float,float,float],Tuple[float,float,float]]]]:
    """Return (file_path, matrix3x3) from the <value> payload. Matrix kept for completeness (unused)."""
    if not isinstance(text, str):
        return None, None
    m_file = re.search(r"file\s*=\s*['\"]([^'\"]+)['\"]", text)
    fpath = m_file.group(1) if m_file else None
    m_mat = re.search(r"matrix\s*=\s*\(([^)]+)\)\s*\(([^)]+)\)\s*\(([^)]+)\)", text)
    H = None
    if m_mat:
        rows = []
        ok = True
        for i in range(1, 4):
            parts = [p.strip() for p in m_mat.group(i).split(",")]
            if len(parts) != 3:
                ok = False
                break
            try:
                rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except Exception:
                ok = False
                break
        if ok:
            H = (rows[0], rows[1], rows[2])
    return fpath, H


def _resolve_path(raw: str, lys_path: Optional[Path]) -> Optional[str]:
    """Resolve raw path as-is, normalize slashes, and try relative to LYS dir."""
    if not raw:
        return None
    cands = [Path(raw)]
    cands.append(Path(raw.replace('\\\\', '\\')))
    cands.append(Path(raw.replace('\\', '/')))
    if lys_path:
        base = lys_path.parent
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


# ---------------- preview dialog (raw only) ----------------
class ImagePreviewDialog(QtWidgets.QDialog):
    """Simple zoomable preview. Transform preview is intentionally disabled in this build."""
    def __init__(self, img_path: str,
                 H_um_from_px=None,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"Preview — {Path(img_path).name}")
        self.resize(1100, 780)

        layout = QtWidgets.QVBoxLayout(self)

        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.view.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        layout.addWidget(self.view, 1)

        bar = QtWidgets.QHBoxLayout()
        self.btn_fit = QtWidgets.QPushButton("Fit")
        self.btn_reset = QtWidgets.QPushButton("100%")
        self.lbl_info = QtWidgets.QLabel("")
        self.lbl_info.setStyleSheet("color:#666;")
        bar.addWidget(self.btn_fit)
        bar.addWidget(self.btn_reset)
        bar.addStretch(1)
        bar.addWidget(self.lbl_info)
        layout.addLayout(bar)

        qimg = QtGui.QImage(img_path)
        if qimg.isNull():
            raise RuntimeError(f"Could not load image:\n{img_path}")
        self._w = qimg.width()
        self._h = qimg.height()
        self._pix = QtGui.QPixmap.fromImage(qimg)

        self._item = QtWidgets.QGraphicsPixmapItem(self._pix)
        self._item.setZValue(0)
        self.scene.addItem(self._item)

        self.view.wheelEvent = self._on_wheel  # type: ignore
        self.btn_fit.clicked.connect(self._fit)
        self.btn_reset.clicked.connect(self._reset)

        self._update_info()
        self._fit()

    def _on_wheel(self, event) -> None:
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else 0
        if delta == 0 and hasattr(event, "pixelDelta"):
            delta = event.pixelDelta().y()
        if delta == 0:
            return
        factor = 1.25 if delta > 0 else 1.0/1.25
        self.view.scale(factor, factor)

    def _fit(self) -> None:
        rect = self._item.mapRectToScene(self._item.boundingRect())
        if rect.isValid() and rect.width() > 0 and rect.height() > 0:
            self.view.fitInView(rect, QtCore.Qt.KeepAspectRatio)

    def _reset(self) -> None:
        self.view.resetTransform()
        self.view.centerOn(self._item)

    def _update_info(self) -> None:
        self.lbl_info.setText(f"{self._w}×{self._h}px  —  Raw pixels (transform preview disabled).  Wheel: zoom, Drag: pan")


# ---------------- single-editor widget (old LYSTab functionality) ----------------
class _SingleLYSEditor(QtWidgets.QWidget):
    fileLoaded = QtCore.Signal(str)
    fileSaved = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self._current_path: Optional[Path] = None
        self._tree: Optional[ET.ElementTree] = None
        self._root: Optional[ET.Element] = None
        self._ordered_parent: Optional[ET.Element] = None
        self._elem_seq = 0
        self._id_to_elem: Dict[int, ET.Element] = {}

        self._build_ui()
        self._wire()
        self._update_buttons()

    def _build_ui(self) -> None:
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0,0,0,0)
        v.setSpacing(8)

        grp_open = QtWidgets.QGroupBox("Open .LYS file")
        v.addWidget(grp_open)
        h = QtWidgets.QHBoxLayout(grp_open)
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("Select a KLayout .lys session file…")
        self.btn_browse = QtWidgets.QPushButton("Browse…")
        self.btn_reload = QtWidgets.QPushButton("Reload")
        h.addWidget(QtWidgets.QLabel("Session file:"))
        h.addWidget(self.path_edit, 1)
        h.addWidget(self.btn_browse)
        h.addWidget(self.btn_reload)

        body = QtWidgets.QWidget()
        v.addWidget(body, 1)
        grid = QtWidgets.QGridLayout(body)
        grid.setContentsMargins(0,0,0,0)
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

        grid.addWidget(QtWidgets.QLabel("Images / annotations (drag to reorder, double-click to preview raw image):"), 0, 0, 1, 2)
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

    def _wire(self) -> None:
        self.btn_browse.clicked.connect(self._browse)
        self.btn_reload.clicked.connect(self.reload)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_save.clicked.connect(self.save)
        self.btn_save_as.clicked.connect(self.save_as)
        self.list.model().rowsMoved.connect(self._reordered)
        self.list.itemDoubleClicked.connect(self._preview_item)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.path_edit.returnPressed.connect(self.reload)

    def _update_buttons(self) -> None:
        has_items = self.list.count() > 0
        any_sel = len(self.list.selectedIndexes()) > 0
        self.btn_up.setEnabled(any_sel and has_items)
        self.btn_down.setEnabled(any_sel and has_items)
        self.btn_delete.setEnabled(any_sel and has_items)
        self.btn_save.setEnabled(has_items and self._tree is not None and self._ordered_parent is not None)
        self.btn_save_as.setEnabled(has_items and self._tree is not None and self._ordered_parent is not None)
        self.btn_reload.setEnabled(self._current_path is not None and self._current_path.exists())

    # ---------- file ops ----------
    def _browse(self) -> None:
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select a .LYS file", "", "KLayout Session (*.lys);;All files (*.*)")
        if p:
            self.path_edit.setText(p)
            self.load(Path(p))

    def reload(self) -> None:
        p = self.path_edit.text().strip()
        if p:
            self.load(Path(p))

    def load(self, path: Path) -> None:
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
        self._elem_seq = 0
        self._id_to_elem.clear()
        self._ordered_parent = None
        self.list.clear()

        elems, parent = self._find_image_elems(root)
        if not elems:
            self._status("No image annotations found.")
            self._update_buttons()
            self.fileLoaded.emit(str(path))
            return

        self._ordered_parent = parent
        for e in elems:
            self._elem_seq += 1
            self._id_to_elem[self._elem_seq] = e
            f, _ = self._file_and_matrix_for_elem(e)
            label = Path(f).name if f else "<image>"
            it = QtWidgets.QListWidgetItem(label)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, self._elem_seq)
            self.list.addItem(it)

        self._status(f"Loaded {len(elems)} items from {path.name}")
        self.fileLoaded.emit(str(path))
        self._update_buttons()

    def _status(self, text: str) -> None:
        self.lbl_status.setText(text)

    # ---------- XML parsing ----------
    def _file_and_matrix_for_elem(self, elem: ET.Element):
        if elem.tag != "annotation":
            return None, None
        cls = elem.find("class")
        if cls is None or (cls.text or "").strip().lower() != "img::object":
            return None, None
        val = elem.find("value")
        if val is None or not isinstance(val.text, str):
            return None, None
        return _parse_value_for_file_and_matrix(val.text)

    def _is_image_elem(self, elem: ET.Element) -> bool:
        f, _ = self._file_and_matrix_for_elem(elem)
        return f is not None

    def _find_image_elems(self, root: ET.Element) -> Tuple[List[ET.Element], Optional[ET.Element]]:
        annotations = root.find(".//annotations")
        if annotations is not None:
            hits = [e for e in list(annotations) if self._is_image_elem(e)]
            if hits:
                return hits, annotations
        # fallback: scan anywhere and return the parent that has the most hits
        parent_hits: Dict[ET.Element, List[ET.Element]] = {}
        for e in root.iter():
            if self._is_image_elem(e):
                parent = self._parent_of(e)
                if parent is not None:
                    parent_hits.setdefault(parent, []).append(e)
        if parent_hits:
            best_parent = max(parent_hits.items(), key=lambda kv: len(kv[1]))[0]
            return parent_hits[best_parent], best_parent
        return [], None

    def _parent_of(self, elem: ET.Element) -> Optional[ET.Element]:
        if self._root is None:
            return None
        for parent in self._root.iter():
            for child in list(parent):
                if child is elem:
                    return parent
        return None

    # ---------- preview ----------
    def _elem_id(self, item: QtWidgets.QListWidgetItem) -> int:
        return int(item.data(QtCore.Qt.ItemDataRole.UserRole))

    def _preview_item(self, item: QtWidgets.QListWidgetItem) -> None:
        elem = self._id_to_elem.get(self._elem_id(item))
        if not elem:
            return
        raw, _H = self._file_and_matrix_for_elem(elem)
        if not raw:
            QtWidgets.QMessageBox.information(self, "No image", "Could not find image path in this annotation.")
            return
        resolved = _resolve_path(raw, self._current_path)
        if not resolved:
            msg = f"Could not find image on disk:\n{raw}"
            if self._current_path:
                msg += f"\n(Tried relative to: {self._current_path.parent})"
            QtWidgets.QMessageBox.warning(self, "File not found", msg)
            return
        try:
            dlg = ImagePreviewDialog(resolved, parent=self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Preview failed", str(e))

    # ---------- editing actions ----------
    def _selected_rows(self) -> List[int]:
        return sorted({idx.row() for idx in self.list.selectedIndexes()})

    def _move_up(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        for r in rows:
            if r > 0:
                self._swap_rows(r, r-1)
        self._restore_selection([r - (1 if r > 0 else 0) for r in rows])
        self._reordered()

    def _move_down(self) -> None:
        rows = sorted(self._selected_rows(), reverse=True)
        if not rows:
            return
        for r in rows:
            if r < self.list.count() - 1:
                self._swap_rows(r, r+1)
        self._restore_selection([r + (1 if r < self.list.count() - 1 else 0) for r in rows])
        self._reordered()

    def _swap_rows(self, i: int, j: int) -> None:
        if i == j:
            return
        it_i = self.list.takeItem(i)
        it_j = self.list.takeItem(j - 1 if j > i else j)
        if it_j is not None:
            self.list.insertItem(i, it_j)
        if it_i is not None:
            self.list.insertItem(j, it_i)

    def _restore_selection(self, rows: List[int]) -> None:
        self.list.clearSelection()
        for r in rows:
            if 0 <= r < self.list.count():
                self.list.item(r).setSelected(True)

    def _delete(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        resp = QtWidgets.QMessageBox.question(
            self, "Delete entries",
            f"Delete {len(rows)} selected item(s) from this session?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        if resp != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        for r in reversed(rows):
            self.list.takeItem(r)
        if self._ordered_parent is not None and self._tree is not None:
            keep_ids = [self._elem_id(self.list.item(i)) for i in range(self.list.count())]
            keep_elems = [self._id_to_elem[i] for i in keep_ids if i in self._id_to_elem]
            for child in list(self._ordered_parent):
                self._ordered_parent.remove(child)
            for e in keep_elems:
                self._ordered_parent.append(e)
            keep_set = set(keep_ids)
            self._id_to_elem = {i: self._id_to_elem[i] for i in keep_set if i in self._id_to_elem}
        self._status("Deleted. (Remember to Save) ")
        self._update_buttons()

    def _reordered(self, *args) -> None:
        if self._ordered_parent is None or self._tree is None:
            return
        ids_in_order = [self._elem_id(self.list.item(i)) for i in range(self.list.count())]
        elems = [self._id_to_elem[i] for i in ids_in_order if i in self._id_to_elem]
        for child in list(self._ordered_parent):
            self._ordered_parent.remove(child)
        for e in elems:
            self._ordered_parent.append(e)
        self._status("Reordered. (Remember to Save) ")
        self._update_buttons()

    # ---------- saving ----------
    def _ensure_backup(self, path: Path) -> None:
        try:
            if path.exists():
                bak = path.with_suffix(path.suffix + ".bak")
                if (not bak.exists()) or (bak.stat().st_size != path.stat().st_size):
                    bak.write_bytes(path.read_bytes())
        except Exception:
            pass

    def save(self) -> None:
        if self._tree is None or self._current_path is None:
            return
        self._ensure_backup(self._current_path)
        try:
            self._tree.write(self._current_path, encoding="utf-8", xml_declaration=True)
            self._status(f"Saved: {self._current_path.name}")
            self.fileSaved.emit(str(self._current_path))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))

    def save_as(self) -> None:
        if self._tree is None:
            return
        p, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save .LYS as…", "", "KLayout Session (*.lys);;All files (*.*)")
        if not p:
            return
        dest = Path(p)
        try:
            self._tree.write(dest, encoding="utf-8", xml_declaration=True)
            self._status(f"Saved as: {dest.name}")
            self.fileSaved.emit(str(dest))
            self._current_path = dest
            self.path_edit.setText(str(dest))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))


# ---------------- NEW: Side-by-side container as the exported LYSTab ----------------
class LYSTab(QtWidgets.QWidget):
    """New .LYS tab: two editors side by side with COPY arrows to move items between sessions."""
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(8)

        panes = QtWidgets.QHBoxLayout()
        outer.addLayout(panes, 1)

        # Left editor
        self.left = _SingleLYSEditor(self)
        left_box = QtWidgets.QVBoxLayout()
        left_box.addWidget(self.left, 1)

        # Middle copy controls
        mid = QtWidgets.QVBoxLayout()
        mid.setSpacing(12)
        self.btn_copy_lr = QtWidgets.QPushButton("→ COPY →")
        self.btn_copy_rl = QtWidgets.QPushButton("← COPY ←")
        for b in (self.btn_copy_lr, self.btn_copy_rl):
            b.setMinimumHeight(40)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setToolTip("Copy selected image annotations to the other .lys")
        mid.addStretch(1)
        mid.addWidget(self.btn_copy_lr)
        mid.addWidget(self.btn_copy_rl)
        mid.addStretch(1)

        # Right editor
        self.right = _SingleLYSEditor(self)
        right_box = QtWidgets.QVBoxLayout()
        right_box.addWidget(self.right, 1)

        # Resizable splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        wL = QtWidgets.QWidget(); wL.setLayout(left_box)
        wM = QtWidgets.QWidget(); wM.setLayout(mid)
        wR = QtWidgets.QWidget(); wR.setLayout(right_box)
        splitter.addWidget(wL)
        splitter.addWidget(wM)
        splitter.addWidget(wR)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(2, 1)
        panes.addWidget(splitter, 1)

        # Status tip
        self.status = QtWidgets.QLabel("Use each pane’s Browse button to open .LYS files. Select items and click a COPY arrow.")
        self.status.setStyleSheet("color:#555;")
        outer.addWidget(self.status)

        # Wire copy actions
        self.btn_copy_lr.clicked.connect(lambda: self._copy_selected(src=self.left, dst=self.right))
        self.btn_copy_rl.clicked.connect(lambda: self._copy_selected(src=self.right, dst=self.left))

    # ----- copy logic reused -----
    def _selected_elem_ids(self, tab: _SingleLYSEditor) -> List[int]:
        return [int(tab.list.item(i).data(QtCore.Qt.UserRole)) for i in range(tab.list.count()) if tab.list.item(i).isSelected()]

    def _copy_selected(self, src: _SingleLYSEditor, dst: _SingleLYSEditor):
        if src._ordered_parent is None or src._tree is None:
            QtWidgets.QMessageBox.information(self, "Nothing to copy", "Open a .LYS file on the source side and select items.")
            return
        if dst._ordered_parent is None or dst._tree is None:
            QtWidgets.QMessageBox.information(self, "No destination", "Open a .LYS file on the destination side.")
            return
        ids = self._selected_elem_ids(src)
        if not ids:
            QtWidgets.QMessageBox.information(self, "Nothing selected", "Select one or more images to copy.")
            return

        elems_to_add: List[ET.Element] = []
        for i in ids:
            elem = src._id_to_elem.get(i)
            if elem is not None:
                elems_to_add.append(deepcopy(elem))

        if not elems_to_add:
            return

        for e in elems_to_add:
            dst._ordered_parent.append(e)

        # Refresh destination list
        dst.list.clear()
        dst._id_to_elem.clear()
        dst._elem_seq = 0
        for child in list(dst._ordered_parent):
            if child.tag != "annotation":
                continue
            f, _ = dst._file_and_matrix_for_elem(child)
            if f is None:
                continue
            dst._elem_seq += 1
            dst._id_to_elem[dst._elem_seq] = child
            label = Path(f).name
            it = QtWidgets.QListWidgetItem(label)
            it.setData(QtCore.Qt.ItemDataRole.UserRole, dst._elem_seq)
            dst.list.addItem(it)

        dst._status(f"Added {len(elems_to_add)} item(s). (Remember to Save)")
        self.status.setText(f"Copied {len(elems_to_add)} item(s).")


# Standalone harness for quick testing
class _Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(".LYS Tab — Side-by-side")
        self.resize(1300, 720)
        self.setCentralWidget(LYSTab(self))


def _main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = _Window()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _main()
