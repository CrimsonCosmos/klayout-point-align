# lys_editor_tab.py
# A self-contained .LYS editor tab for PySide6/Qt
# Features: open, parse image-like entries, show list, reorder, delete, save / save as
#
# Integration in align_gui_aqua_qt.py:
#   from lys_editor_tab import LYSTab
#   ...
#   self.lys_tab = LYSTab(parent=self)
#   self.tabs.addTab(self.lys_tab, ".LYS file editing")
#
# You can also run this file directly to test standalone:
#   python lys_editor_tab.py

from __future__ import annotations
import os
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

class _ListItem(QtWidgets.QListWidgetItem):
    """
    Carries a pointer (id) to the XML element we parsed for this row.
    We store a stable integer id and look up the ET.Element via a dict, so
    we never keep stale references if we reload/replace the tree.
    """
    def __init__(self, display: str, elem_id: int):
        super().__init__(display)
        self.setData(QtCore.Qt.ItemDataRole.UserRole, elem_id)


class LYSTab(QtWidgets.QWidget):
    """
    A QWidget you can add as a tab into your existing app.
    Focus: simple, reliable editing of order & deletion for image-like annotations.
    """
    fileLoaded = QtCore.Signal(str)
    fileSaved = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("LYSEditorTab")

        # XML state
        self._current_path: Optional[Path] = None
        self._tree: Optional[ET.ElementTree] = None
        self._root: Optional[ET.Element] = None

        # We assign an incremental ID to each parsed element and keep a map.
        self._elem_seq = 0
        self._id_to_elem: Dict[int, ET.Element] = {}
        self._ordered_parent: Optional[ET.Element] = None  # Parent whose children we reorder

        self._build_ui()
        self._wire_logic()
        self._update_buttons_enabled()

    # ---------------- UI ----------------
    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # --- Open group ---
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

        # --- List + controls ---
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
        self.btn_up.setAutoDefault(False)
        self.btn_down.setAutoDefault(False)
        self.btn_delete.setAutoDefault(False)
        btns.addWidget(self.btn_up)
        btns.addWidget(self.btn_down)
        btns.addSpacing(8)
        btns.addWidget(self.btn_delete)
        btns.addStretch(1)

        grid.addWidget(QtWidgets.QLabel("Images / annotations (drag to reorder):"), 0, 0, 1, 2)
        grid.addWidget(self.list, 1, 0, 1, 1)
        grid.addLayout(btns, 1, 1, 1, 1)

        # --- Save bar ---
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

        # Accessibility / shortcuts
        self.btn_delete.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Delete))
        self.btn_save.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        self.btn_save_as.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.btn_up.setShortcut(QtGui.QKeySequence("Alt+Up"))
        self.btn_down.setShortcut(QtGui.QKeySequence("Alt+Down"))

    def _wire_logic(self):
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

    # ------------- Helpers / State -------------
    def _update_buttons_enabled(self):
        has_items = self.list.count() > 0
        any_selected = len(self.list.selectedIndexes()) > 0
        self.btn_up.setEnabled(any_selected and has_items)
        self.btn_down.setEnabled(any_selected and has_items)
        self.btn_delete.setEnabled(any_selected and has_items)
        self.btn_save.setEnabled(has_items and self._tree is not None and self._ordered_parent is not None)
        self.btn_save_as.setEnabled(has_items and self._tree is not None and self._ordered_parent is not None)
        self.btn_reload.setEnabled(self._current_path is not None and self._current_path.exists())

    def _browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select a .LYS file", "", "KLayout Session (*.lys);;All files (*.*)"
        )
        if path:
            self.path_edit.setText(path)
            self.load(Path(path))

    def reload(self):
        p = self.path_edit.text().strip()
        if p:
            self.load(Path(p))

    def _status(self, text: str):
        self.lbl_status.setText(text)

    # ------------- Parsing -------------
    def load(self, path: Path):
        """Load and parse a .lys file into the list."""
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

        # Reset state
        self._current_path = path
        self._tree = tree
        self._root = root
        self._id_to_elem.clear()
        self._elem_seq = 0
        self._ordered_parent = None
        self.list.clear()

        # Heuristic 1: Many KLayout sessions store image annotations under <annotations>.
        # We’ll prefer that block if present; otherwise we do a generic scan and reorder within the first parent that yields hits.
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
        """
        Return ([elements], parent_for_reordering).
        Strategy:
        1) Look for <annotations>…</annotations> and collect children that reference image files.
        2) Fallback: global scan for elements with attributes/children pointing to image paths;
           then return the parent of the first batch of siblings as the reorder scope.
        """
        # Strategy 1: annotations block
        annotations = root.find(".//annotations")
        if annotations is not None:
            hits = [e for e in list(annotations) if self._element_is_image_like(e)]
            if hits:
                return hits, annotations

        # Strategy 2: generic scan — group by parent
        parent_to_hits: Dict[ET.Element, List[ET.Element]] = {}
        for e in root.iter():
            if self._element_is_image_like(e):
                parent = self._parent_of(e)
                if parent is not None:
                    parent_to_hits.setdefault(parent, []).append(e)

        # choose the parent with the most hits
        if parent_to_hits:
            best_parent = max(parent_to_hits.items(), key=lambda kv: len(kv[1]))[0]
            return parent_to_hits[best_parent], best_parent

        return [], None

    def _element_is_image_like(self, elem: ET.Element) -> bool:
        """
        Heuristics to decide if an element corresponds to an image annotation entry:
        - attribute values that look like image file paths
        - tag names commonly used for images (e.g., 'image', 'pixmap') with a 'path' attribute
        - KLayout custom annotations sometimes encode 'img::' in names or types
        """
        # Common attribute keys that might hold a path
        for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href"):
            v = elem.attrib.get(key)
            if v and _is_image_path(v):
                return True

        # scan any attribute for an image path
        for v in elem.attrib.values():
            if isinstance(v, str) and _is_image_path(v):
                return True

        # img:: marker in names
        name = elem.attrib.get("name") or elem.attrib.get("object-name") or ""
        if "img::" in name.lower():
            return True

        # child nodes with @path like patterns
        for child in list(elem):
            for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href", "value"):
                v = child.attrib.get(key)
                if v and _is_image_path(v):
                    return True

        return False

    def _describe_elem(self, elem: ET.Element) -> str:
        """
        Build a readable label for the list (best-effort).
        """
        candidates = []
        # prioritize path-like attributes
        for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href"):
            v = elem.attrib.get(key)
            if v:
                candidates.append(v)

        # other attributes that might help identify
        for key in ("name", "object-name", "label", "type"):
            v = elem.attrib.get(key)
            if v:
                candidates.append(v)

        # children attributes
        for child in list(elem):
            for key in ("file", "filename", "path", "src", "url", "image", "pixmap", "href", "value"):
                v = child.attrib.get(key)
                if v:
                    candidates.append(v)

        if candidates:
            # Just show the last path segment if it looks like a path, otherwise raw
            display = candidates[0]
            try:
                pn = Path(display)
                if pn.suffix and pn.name:
                    display = pn.name
            except Exception:
                pass
            return display

        # fallback: tag name and some attrs
        attrs = " ".join(f'{k}="{v}"' for k, v in list(elem.attrib.items())[:2])
        return f"<{elem.tag} {attrs}>".strip()

    def _parent_of(self, elem: ET.Element) -> Optional[ET.Element]:
        # xml.etree doesn't have parent pointers; we reconstruct by walking.
        if self._root is None:
            return None
        for parent in self._root.iter():
            for child in list(parent):
                if child is elem:
                    return parent
        return None

    # --------- Editing actions ----------
    def _selected_rows(self) -> List[int]:
        rows = sorted({idx.row() for idx in self.list.selectedIndexes()})
        return rows

    def _move_up_clicked(self):
        rows = self._selected_rows()
        if not rows:
            return
        for r in rows:
            if r > 0:
                self._swap_rows(r, r - 1)
        # keep selection on moved items
        self._restore_selection([r - (1 if r > 0 else 0) for r in rows])
        self._list_reordered()

    def _move_down_clicked(self):
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

    def _delete_clicked(self):
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

        # Remove list items visually first
        for r in reversed(rows):
            self.list.takeItem(r)

        # Update XML: remove corresponding elements from parent
        if self._ordered_parent is not None and self._tree is not None:
            keep_ids = [self._item_elem_id(self.list.item(i)) for i in range(self.list.count())]
            keep_elems = [self._id_to_elem[i] for i in keep_ids if i in self._id_to_elem]

            # Clear and reappend in current order
            for child in list(self._ordered_parent):
                self._ordered_parent.remove(child)
            for e in keep_elems:
                self._ordered_parent.append(e)

            # Also prune _id_to_elem for removed entries
            keep_set = set(keep_ids)
            self._id_to_elem = {i: self._id_to_elem[i] for i in keep_set if i in self._id_to_elem}

        self._status("Deleted. (Remember to Save) ")
        self._update_buttons_enabled()

    def _item_elem_id(self, item: QtWidgets.QListWidgetItem) -> int:
        return int(item.data(QtCore.Qt.ItemDataRole.UserRole))

    def _list_reordered(self, *args):
        # When the QListWidget order changes (by drag/drop or Up/Down),
        # rewrite the children order in the XML parent.
        if self._ordered_parent is None or self._tree is None:
            return
        ids_in_order = [self._item_elem_id(self.list.item(i)) for i in range(self.list.count())]
        elems = [self._id_to_elem[i] for i in ids_in_order if i in self._id_to_elem]

        # Clear and re-append in new order
        for child in list(self._ordered_parent):
            self._ordered_parent.remove(child)
        for e in elems:
            self._ordered_parent.append(e)

        self._status("Reordered. (Remember to Save) ")
        self._update_buttons_enabled()

    # -------------- Saving --------------
    def _ensure_backup(self, path: Path):
        """Create a lightweight .bak alongside original before overwriting."""
        try:
            if path.exists():
                bak = path.with_suffix(path.suffix + ".bak")
                # Only create/overwrite a .bak if it doesn't exist or file changed in size
                if (not bak.exists()) or (bak.stat().st_size != path.stat().st_size):
                    bak.write_bytes(path.read_bytes())
        except Exception:
            pass  # best effort

    def save(self):
        if self._tree is None or self._current_path is None:
            return
        self._ensure_backup(self._current_path)
        try:
            self._tree.write(self._current_path, encoding="utf-8", xml_declaration=True)
            self._status(f"Saved: {self._current_path.name}")
            self.fileSaved.emit(str(self._current_path))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))

    def save_as(self):
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
            # Update current file pointer so subsequent Save() overwrites the new one
            self._current_path = dest
            self.path_edit.setText(str(dest))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(e))


# ---------- Standalone testing ----------
class _Window(QtWidgets.QMainWindow):
    def __init__(self):
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
