
# lys_editor_tab.py — Single-mode by default, one-click Dual Mode (copy images)
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
import os

from qt_compat import QtCore, QtGui, QtWidgets

IMG_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}


# ---------------- helpers ----------------
def _parse_value_for_file_and_matrix(text: str):
    """Return (file_path, matrix3x3 or None) parsed from <value> payload. Matrix kept for completeness (unused)."""
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


def _set_value_file(text: str, new_path: str) -> str:
    """Return value text with file='...' replaced safely (preserve everything else)."""
    if ':' in new_path and '\\' in new_path:
        new_path_escaped = new_path.replace('\\', '\\\\')
    else:
        new_path_escaped = new_path
    if re.search(r"file\s*=", text):
        return re.sub(r"file\s*=\s*(['\"]).*?\1", f"file='{new_path_escaped}'", text)
    return text.strip() + f";file='{new_path_escaped}'"


# ---------------- preview dialog (raw only) ----------------
class ImagePreviewDialog(QtWidgets.QDialog):
    """Simple zoomable preview. Transform preview is intentionally disabled in this build."""
    def __init__(self, img_path: str, parent: Optional[QtWidgets.QWidget] = None):
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


# ---------------- single-editor widget with MULTI-GDS + rename ----------------
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

        # Create default save directory
        self._default_save_dir = Path(__file__).parent / "lys_sessions"
        self._default_save_dir.mkdir(exist_ok=True)

        self._build_ui()
        self._wire()
        self._update_buttons()

    # ---- UI ----
    def _build_ui(self) -> None:
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0,0,0,0)
        v.setSpacing(8)

        # Top: open
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

        # MULTI-GDS controls
        grp_gds = QtWidgets.QGroupBox("Layouts (.gds / .oasis) — multiple allowed")
        v.addWidget(grp_gds)
        g = QtWidgets.QGridLayout(grp_gds)
        self.gds_list = QtWidgets.QListWidget()
        self.gds_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.btn_gds_add = QtWidgets.QPushButton("Add…")
        self.btn_gds_remove = QtWidgets.QPushButton("Remove")
        self.btn_gds_rename = QtWidgets.QPushButton("Rename…")
        self.btn_gds_open = QtWidgets.QPushButton("Open Folder")
        g.addWidget(self.gds_list, 0, 0, 1, 6)
        g.addWidget(self.btn_gds_add, 1, 0)
        g.addWidget(self.btn_gds_remove, 1, 1)
        g.addWidget(self.btn_gds_rename, 1, 2)
        g.addWidget(self.btn_gds_open, 1, 3)
        g.setColumnStretch(5, 1)

        # Body
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
        self.list.setUniformItemSizes(False)  # Allow variable sizes for thumbnails
        self.list.setIconSize(QtCore.QSize(80, 80))  # Set thumbnail size
        self.list.setSpacing(2)  # Add spacing between items
        self.list.setContextMenuPolicy(QtCore.Qt.NoContextMenu)  # Disable rename context menu

        btns = QtWidgets.QVBoxLayout()
        self.btn_up = QtWidgets.QPushButton("Up")
        self.btn_down = QtWidgets.QPushButton("Down")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_rename = QtWidgets.QPushButton("Rename…")
        for b in (self.btn_up, self.btn_down, self.btn_delete, self.btn_rename):
            b.setAutoDefault(False)
        btns.addWidget(self.btn_up)
        btns.addWidget(self.btn_down)
        btns.addSpacing(8)
        btns.addWidget(self.btn_delete)
        btns.addSpacing(8)
        btns.addWidget(self.btn_rename)
        btns.addStretch(1)

        grid.addWidget(QtWidgets.QLabel("Images / annotations (drag to reorder, double-click to preview raw image):"), 0, 0, 1, 2)
        grid.addWidget(self.list, 1, 0, 1, 1)
        grid.addLayout(btns, 1, 1, 1, 1)

        # Save bar
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
        self.btn_rename.setShortcut(QtGui.QKeySequence("F2"))

        # Disable/hide rename buttons for GDS and images
        self.btn_rename.setVisible(False)
        self.btn_rename.setEnabled(False)
        self.btn_gds_rename.setVisible(False)
        self.btn_gds_rename.setEnabled(False)

    def _wire(self) -> None:
        # File top
        self.btn_browse.clicked.connect(self._browse)
        self.btn_reload.clicked.connect(self.reload)
        # MULTI-GDS
        self.btn_gds_add.clicked.connect(self._gds_add)
        self.btn_gds_remove.clicked.connect(self._gds_remove)
        self.btn_gds_rename.clicked.connect(self._gds_rename)
        self.btn_gds_open.clicked.connect(self._gds_open_folder)
        self.gds_list.itemSelectionChanged.connect(self._update_buttons)
        # List actions
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_rename.clicked.connect(self._rename_selected_image)
        self.list.model().rowsMoved.connect(self._reordered)
        self.list.itemDoubleClicked.connect(self._preview_item)
        self.list.itemSelectionChanged.connect(self._update_buttons)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.path_edit.returnPressed.connect(self.reload)
        # Save buttons
        self.btn_save.clicked.connect(self.save)
        self.btn_save_as.clicked.connect(self.save_as)

    # ---- MULTI-GDS helpers ----
    def _iter_layouts(self) -> List[ET.Element]:
        if self._root is None:
            return []
        return [el for el in self._root.iter("layout")]

    def _gds_refresh_list(self) -> None:
        self.gds_list.clear()
        for lay in self._iter_layouts():
            fp = (lay.findtext("file-path") or "").strip()
            nm = (lay.findtext("name") or "").strip()
            label = Path(fp).name if fp else (nm or "<unnamed layout>")
            it = QtWidgets.QListWidgetItem(label)
            it.setToolTip(fp or nm or "")
            it.setData(QtCore.Qt.UserRole, fp)
            self.gds_list.addItem(it)

    def _gds_add(self) -> None:
        if self._root is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Add GDS", "", "Layout Files (*.gds *.gds2 *.oasis);;All files (*.*)")
        if not path:
            return
        lay = ET.SubElement(self._root, "layout")
        ET.SubElement(lay, "file-path").text = path
        ET.SubElement(lay, "name").text = Path(path).name
        self._gds_refresh_list()
        self._status("Added GDS. (Remember to Save)")

    def _gds_remove(self) -> None:
        if self._root is None:
            return
        rows = [idx.row() for idx in self.gds_list.selectedIndexes()]
        if not rows:
            return
        layouts = self._iter_layouts()
        rows = sorted(set(rows), reverse=True)
        for r in rows:
            if 0 <= r < len(layouts):
                self._root.remove(layouts[r])
        self._gds_refresh_list()
        self._status("Removed selected GDS. (Remember to Save)")

    def _gds_rename(self) -> None:
        rows = [idx.row() for idx in self.gds_list.selectedIndexes()]
        if len(rows) != 1:
            QtWidgets.QMessageBox.information(self, "Select one", "Select exactly one GDS to rename.")
            return
        r = rows[0]
        layouts = self._iter_layouts()
        if not (0 <= r < len(layouts)):
            return
        lay = layouts[r]
        fp_el = lay.find("file-path")
        if fp_el is None or not fp_el.text:
            QtWidgets.QMessageBox.information(self, "No path", "This <layout> has no file-path.")
            return
        old = Path(fp_el.text)
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename GDS", "New filename:", text=old.name)
        if not ok or not new_name.strip():
            return
        dest = old.parent / new_name.strip()
        try:
            old.rename(dest)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Rename failed", str(e))
            return
        # Update XML
        fp_el.text = str(dest)
        name_el = lay.find("name") or ET.SubElement(lay, "name")
        name_el.text = dest.name
        self._gds_refresh_list()
        self._status(f"Renamed GDS to {dest.name}. (Remember to Save)")

    def _gds_open_folder(self) -> None:
        rows = [idx.row() for idx in self.gds_list.selectedIndexes()]
        if len(rows) != 1:
            return
        layouts = self._iter_layouts()
        r = rows[0]
        if not (0 <= r < len(layouts)):
            return
        fp = (layouts[r].findtext("file-path") or "").strip()
        if not fp:
            return
        folder = str(Path(fp).parent)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    # ---- Image rename ----
    def _context_menu(self, pos: QtCore.QPoint) -> None:
        if not self.list.selectedItems():
            return
        m = QtWidgets.QMenu(self)
        a = m.addAction("Rename…")
        a.triggered.connect(self._rename_selected_image)
        m.exec(self.list.mapToGlobal(pos))

    def _rename_selected_image(self) -> None:
        rows = [idx.row() for idx in self.list.selectedIndexes()]
        if len(rows) != 1:
            QtWidgets.QMessageBox.information(self, "Select one", "Please select exactly one image to rename.")
            return
        item = self.list.item(rows[0])
        elem = self._id_to_elem.get(int(item.data(QtCore.Qt.UserRole)))
        if elem is None:
            return
        raw, _ = self._file_and_matrix_for_elem(elem)
        if not raw:
            QtWidgets.QMessageBox.warning(self, "No file", "This annotation has no file= path.")
            return
        resolved = _resolve_path(raw, self._current_path)
        if not resolved:
            QtWidgets.QMessageBox.warning(self, "Not found", f"Could not resolve on disk:\n{raw}")
            return
        old = Path(resolved)
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename image", "New filename (no path):", text=old.name)
        if not ok or not new_name.strip():
            return
        dest = old.parent / new_name.strip()
        if dest.exists():
            resp = QtWidgets.QMessageBox.question(self, "Overwrite?", f"{dest.name} exists. Overwrite?",
                                                  QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if resp != QtWidgets.QMessageBox.Yes:
                return
        try:
            old.rename(dest)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Rename failed", str(e))
            return
        # update XML value
        val = elem.find("value")
        if val is not None and isinstance(val.text, str):
            new_path = str(dest)
            if self._current_path:
                try:
                    rel = os.path.relpath(new_path, start=str(self._current_path.parent))
                    new_path = rel
                except Exception:
                    pass
            val.text = _set_value_file(val.text, new_path)
        # update UI label
        item.setText(dest.name)
        self._status(f"Renamed image to {dest.name}. (Remember to Save)")

    # ---- Core logic ----
    def _update_buttons(self) -> None:
        has_items = self.list.count() > 0
        any_sel = len(self.list.selectedIndexes()) > 0
        self.btn_up.setEnabled(any_sel and has_items)
        self.btn_down.setEnabled(any_sel and has_items)
        self.btn_delete.setEnabled(any_sel and has_items)
        self.btn_rename.setEnabled(any_sel and has_items and len(self.list.selectedIndexes()) == 1)
        self.btn_save.setEnabled(self._tree is not None and self._ordered_parent is not None)
        self.btn_save_as.setEnabled(self._tree is not None and self._ordered_parent is not None)
        self.btn_reload.setEnabled(self._current_path is not None and self._current_path.exists())

        # GDS state
        self.btn_gds_remove.setEnabled(len(self.gds_list.selectedIndexes()) > 0)
        self.btn_gds_rename.setEnabled(len(self.gds_list.selectedIndexes()) == 1)
        self.btn_gds_open.setEnabled(len(self.gds_list.selectedIndexes()) == 1)

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

        # Refresh GDS list
        self._gds_refresh_list()

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

            # Add thumbnail preview
            if f:
                resolved = _resolve_path(f, self._current_path)
                print(f"Image path: {f}, Resolved: {resolved}")  # Debug
                if resolved:
                    thumbnail = self._create_thumbnail(resolved)
                    if thumbnail:
                        print(f"  -> Thumbnail created: {thumbnail.width()}x{thumbnail.height()}")  # Debug
                        it.setIcon(QtGui.QIcon(thumbnail))
                    else:
                        print(f"  -> Thumbnail creation failed")  # Debug

            self.list.addItem(it)

        self._status(f"Loaded {len(elems)} items from {path.name}")
        self.fileLoaded.emit(str(path))
        self._update_buttons()

    def _status(self, text: str) -> None:
        self.lbl_status.setText(text)

    def _create_thumbnail(self, img_path: str, size: int = 80) -> Optional[QtGui.QPixmap]:
        """Create a thumbnail pixmap from an image file."""
        try:
            qimg = QtGui.QImage(img_path)
            if qimg.isNull():
                return None
            # Scale to thumbnail size while maintaining aspect ratio
            pixmap = QtGui.QPixmap.fromImage(qimg)
            return pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        except Exception as e:
            # Debug: print error if thumbnail creation fails
            print(f"Failed to create thumbnail for {img_path}: {e}")
            return None

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

    def _find_image_elems(self, root: ET.Element):
        annotations = root.find(".//annotations")
        if annotations is not None:
            hits = [e for e in list(annotations) if self._is_image_elem(e)]
            if hits:
                return hits, annotations
        # fallback
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
                # Store backups in lys_sessions/backups folder, not next to original
                backup_dir = self._default_save_dir / "backups"
                backup_dir.mkdir(exist_ok=True)

                # Use original filename for backup
                bak = backup_dir / f"{path.name}.bak"

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
        # Default to lys_sessions folder if current path is not set or is on Desktop
        default_dir = str(self._default_save_dir)
        if self._current_path:
            # Check if current file is on Desktop
            try:
                desktop = Path.home() / "Desktop"
                if self._current_path.parent == desktop:
                    # File is on Desktop, redirect to lys_sessions
                    default_dir = str(self._default_save_dir / self._current_path.name)
                else:
                    default_dir = str(self._current_path)
            except Exception:
                pass

        p, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save .LYS as…", default_dir, "KLayout Session (*.lys);;All files (*.*)")
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


# ---------------- LYSTab with single/dual toggle ----------------
class LYSTab(QtWidgets.QWidget):
    """Defaults to single-editor mode. Click the button to show/hide second editor."""
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._dual_visible = False
        self._dual_created = False
        self._outer = QtWidgets.QHBoxLayout(self)
        self._outer.setContentsMargins(0,0,0,0)
        self._outer.setSpacing(8)

        # Left: main editor
        self.left = _SingleLYSEditor(self)
        self._outer.addWidget(self.left, 1)

        # Right: toggle button placeholder (visible in single mode)
        self._right_holder = QtWidgets.QWidget(self)
        right_layout = QtWidgets.QVBoxLayout(self._right_holder)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.addStretch(1)
        self.btn_toggle_dual = QtWidgets.QPushButton("Show Second Editor\n▶")
        self.btn_toggle_dual.setMinimumWidth(220)
        self.btn_toggle_dual.setMinimumHeight(120)
        self.btn_toggle_dual.setStyleSheet("font-size:16px; font-weight:600;")
        right_layout.addWidget(self.btn_toggle_dual, alignment=QtCore.Qt.AlignCenter)
        right_layout.addStretch(1)
        self._outer.addWidget(self._right_holder, 0)

        self.btn_toggle_dual.clicked.connect(self._toggle_dual_mode)

        # Pre-create right editor and mid controls (hidden until enabled)
        self._mid_holder = None
        self.right = None

    # ----- dual mode toggle -----
    def _toggle_dual_mode(self):
        if not self._dual_created:
            self._create_dual_mode()

        # Toggle visibility
        self._dual_visible = not self._dual_visible

        if self._dual_visible:
            # Show second editor (hide button, show mid+right)
            self._right_holder.hide()
            if self._mid_holder:
                self._mid_holder.show()
            if self.right:
                self.right.show()
        else:
            # Hide second editor (show button, hide mid+right)
            if self._mid_holder:
                self._mid_holder.hide()
            if self.right:
                self.right.hide()
            self._right_holder.show()

    def _create_dual_mode(self):
        """Create the dual editor UI on first toggle"""
        if self._dual_created:
            return
        self._dual_created = True

        # Middle copy controls
        self._mid_holder = QtWidgets.QWidget(self)
        mid = QtWidgets.QVBoxLayout(self._mid_holder)
        mid.setSpacing(10)

        # Close button at top
        self.btn_close_dual = QtWidgets.QPushButton("✕ Hide Second Editor")
        self.btn_close_dual.setStyleSheet("font-weight: bold; color: #c00;")
        self.btn_close_dual.setMinimumHeight(40)
        self.btn_close_dual.setCursor(QtCore.Qt.PointingHandCursor)
        mid.addWidget(self.btn_close_dual)

        mid.addStretch(1)

        self.btn_copy_lr = QtWidgets.QPushButton("→ COPY IMAGES →")
        self.btn_copy_rl = QtWidgets.QPushButton("← COPY IMAGES ←")
        self.btn_copy_gds_lr = QtWidgets.QPushButton("→ COPY GDS →")
        self.btn_copy_gds_rl = QtWidgets.QPushButton("← COPY GDS ←")
        for b in (self.btn_copy_lr, self.btn_copy_rl, self.btn_copy_gds_lr, self.btn_copy_gds_rl):
            b.setMinimumHeight(36)
            b.setCursor(QtCore.Qt.PointingHandCursor)

        # Hide GDS copy buttons
        self.btn_copy_gds_lr.setVisible(False)
        self.btn_copy_gds_rl.setVisible(False)

        mid.addWidget(self.btn_copy_lr)
        mid.addWidget(self.btn_copy_rl)
        mid.addStretch(1)

        # Right editor
        self.right = _SingleLYSEditor(self)

        # Add mid controls and right editor to the main layout (after left, before right_holder)
        self._outer.insertWidget(1, self._mid_holder, 0)  # Insert at index 1, stretch 0
        self._outer.insertWidget(2, self.right, 1)  # Insert at index 2, stretch 1

        # Initially hidden
        self._mid_holder.hide()
        self.right.hide()

        # Wire copy actions
        self.btn_copy_lr.clicked.connect(lambda: self._copy_selected_images(src=self.left, dst=self.right))
        self.btn_copy_rl.clicked.connect(lambda: self._copy_selected_images(src=self.right, dst=self.left))
        self.btn_copy_gds_lr.clicked.connect(lambda: self._copy_selected_gds(src=self.left, dst=self.right))
        self.btn_copy_gds_rl.clicked.connect(lambda: self._copy_selected_gds(src=self.right, dst=self.left))

        # Wire close button
        self.btn_close_dual.clicked.connect(self._toggle_dual_mode)

    # ----- copy logic (images) -----
    def _selected_image_ids(self, tab: _SingleLYSEditor) -> List[int]:
        return [int(tab.list.item(i).data(QtCore.Qt.UserRole)) for i in range(tab.list.count()) if tab.list.item(i).isSelected()]

    def _copy_selected_images(self, src: _SingleLYSEditor, dst: _SingleLYSEditor):
        if src._ordered_parent is None or src._tree is None:
            QtWidgets.QMessageBox.information(self, "Nothing to copy", "Open a .LYS file on the source side and select images.")
            return
        if dst._ordered_parent is None or dst._tree is None:
            QtWidgets.QMessageBox.information(self, "No destination", "Open a .LYS file on the destination side.")
            return
        ids = self._selected_image_ids(src)
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

        dst._status(f"Added {len(elems_to_add)} image(s). (Remember to Save)")

    # ----- copy logic (GDS) -----
    def _selected_gds_rows(self, tab: _SingleLYSEditor) -> List[int]:
        return [idx.row() for idx in tab.gds_list.selectedIndexes()]

    def _copy_selected_gds(self, src: _SingleLYSEditor, dst: _SingleLYSEditor):
        if src._root is None:
            QtWidgets.QMessageBox.information(self, "No source", "Open a .LYS file on the source side and select GDS rows.")
            return
        if dst._root is None:
            QtWidgets.QMessageBox.information(self, "No destination", "Open a .LYS file on the destination side.")
            return
        rows = self._selected_gds_rows(src)
        if not rows:
            QtWidgets.QMessageBox.information(self, "Nothing selected", "Select one or more GDS rows to copy.")
            return

        src_layouts = [el for el in src._root.iter("layout")]
        dst_layouts = [el for el in dst._root.iter("layout")]
        dst_paths = set((el.findtext("file-path") or "").strip() for el in dst_layouts)

        add_count = 0
        skip_count = 0
        for r in rows:
            if 0 <= r < len(src_layouts):
                el = src_layouts[r]
                # dedupe by file-path
                fp = (el.findtext("file-path") or "").strip()
                if fp and fp in dst_paths:
                    skip_count += 1
                    continue
                dst._root.append(deepcopy(el))
                if fp:
                    dst_paths.add(fp)
                add_count += 1

        dst._gds_refresh_list()
        msg = f"Copied {add_count} GDS"
        if skip_count:
            msg += f" (skipped {skip_count} duplicate by file-path)"
        msg += ". (Remember to Save)"
        dst._status(msg)


# Standalone harness for quick testing
class _Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(".LYS Tab — Single/Dual Toggle")
        self.resize(1300, 800)
        self.setCentralWidget(LYSTab(self))


def _main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = _Window()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _main()
