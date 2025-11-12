
# gui/align_tab.py
# Self-contained AlignTab widget that builds argv and exposes log/progress hooks.

from __future__ import annotations
import datetime
from pathlib import Path
from typing import List, Optional, Dict
import json

from qt_compat import QtCore, QtGui, QtWidgets
from diagnostic_logger import get_logger
from landmark_presets import LandmarkPresetManager

# ---- Constants mirrored from the legacy main ----
APP_TITLE = "Point Align v1.1"
COMBINED_FILENAME = "session_combined.lys"
PREFS_NAME = "align_gui_prefs.json"
LANDMARKS_PREFS_NAME = "landmark_presets.json"

# Template .lys shipped with the app
LYS_BASENAME = "Test_with_img.lys"

# Canonical GDS for PW Group users (ship alongside app)
GDS_BASENAME = "Test.GDS"

DEFAULT_AFTER_POINTS = "(-50,60),(70,60),(-50,-60),(70,-60)"  # TL, TR, BL, BR (µm)
ALWAYS_AUTO_REVIEW = True

def resource_path(rel_path: str) -> Path:
    base = Path(getattr(__import__("sys").modules["sys"], "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel_path


class ImageStripWidget(QtWidgets.QWidget):
    """Custom widget representing a single image with full alignment controls."""

    alignRequested = QtCore.Signal(str, str, str)  # emits (image_path, landmark_preset, output_file)
    checkStateChanged = QtCore.Signal(str, bool)  # emits (path, checked)
    coordinatesChanged = QtCore.Signal(str, str)  # emits (path, coordinates)

    def __init__(self, image_path: str, available_presets: list, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.image_path = image_path
        self.available_presets = available_presets
        self.selected_coordinates = ""  # Will store the 4 clicked points
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Checkbox
        self.checkbox = QtWidgets.QCheckBox()
        self.checkbox.setToolTip("Select this image for batch operations")
        self.checkbox.stateChanged.connect(self._on_check_changed)
        layout.addWidget(self.checkbox)

        # 1. Select Image (display only - already selected)
        image_section = QtWidgets.QVBoxLayout()
        image_section.setSpacing(2)

        thumbnail_label = QtWidgets.QLabel()
        thumbnail = self._create_thumbnail(self.image_path, 48)
        if thumbnail:
            thumbnail_label.setPixmap(thumbnail)
        else:
            thumbnail_label.setText("[No preview]")
        thumbnail_label.setFixedSize(48, 48)
        thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        image_section.addWidget(thumbnail_label)

        name_label = QtWidgets.QLabel(Path(self.image_path).name)
        name_label.setToolTip(self.image_path)
        name_label.setMaximumWidth(150)
        name_label.setWordWrap(True)
        image_section.addWidget(name_label)
        layout.addLayout(image_section)

        # 2. Selected Coordinates
        coord_section = QtWidgets.QVBoxLayout()
        coord_section.setSpacing(2)
        coord_label = QtWidgets.QLabel("Coordinates:")
        coord_label.setStyleSheet("font-weight: bold;")
        coord_section.addWidget(coord_label)

        self.coord_display = QtWidgets.QLineEdit()
        self.coord_display.setReadOnly(True)
        self.coord_display.setPlaceholderText("Not yet selected")
        self.coord_display.setMinimumWidth(180)
        self.coord_display.setToolTip("The 4 fiducial points clicked on the image")
        coord_section.addWidget(self.coord_display)

        btn_select_coords = QtWidgets.QPushButton("Pick Points")
        btn_select_coords.setToolTip("Click to select 4 fiducial points on the image")
        btn_select_coords.clicked.connect(self._on_pick_points)
        coord_section.addWidget(btn_select_coords)
        layout.addLayout(coord_section)

        # 3. Select GDS Landmarks dropdown
        landmark_section = QtWidgets.QVBoxLayout()
        landmark_section.setSpacing(2)
        landmark_label = QtWidgets.QLabel("GDS Landmarks:")
        landmark_label.setStyleSheet("font-weight: bold;")
        landmark_section.addWidget(landmark_label)

        self.landmark_combo = QtWidgets.QComboBox()
        self.landmark_combo.addItems(self.available_presets)
        self.landmark_combo.setCurrentText("[Default]")
        self.landmark_combo.setToolTip("Select which GDS landmark preset to use")
        self.landmark_combo.setMinimumWidth(120)
        landmark_section.addWidget(self.landmark_combo)
        layout.addLayout(landmark_section)

        # 4. Select Output File
        output_section = QtWidgets.QVBoxLayout()
        output_section.setSpacing(2)
        output_label = QtWidgets.QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold;")
        output_section.addWidget(output_label)

        self.output_field = QtWidgets.QLineEdit()
        self.output_field.setPlaceholderText("Auto-generated")
        self.output_field.setMinimumWidth(150)
        self.output_field.setToolTip("Leave empty for auto-generated filename")
        output_section.addWidget(self.output_field)

        btn_browse_output = QtWidgets.QPushButton("Browse...")
        btn_browse_output.clicked.connect(self._on_browse_output)
        output_section.addWidget(btn_browse_output)
        layout.addLayout(output_section)

        # 5. Run button
        self.run_btn = QtWidgets.QPushButton("Run")
        self.run_btn.setToolTip("Align this image now")
        self.run_btn.setMinimumWidth(80)
        self.run_btn.clicked.connect(self._on_run_clicked)
        layout.addWidget(self.run_btn)

    def _create_thumbnail(self, img_path: str, size: int = 48) -> Optional[QtGui.QPixmap]:
        """Create a thumbnail pixmap from an image file."""
        try:
            qimg = QtGui.QImage(img_path)
            if qimg.isNull():
                return None
            pixmap = QtGui.QPixmap.fromImage(qimg)
            return pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        except Exception:
            return None

    def _on_pick_points(self):
        """Launch point picker for this image."""
        try:
            from klayout_point_align.picker import pick_points_gui

            # Launch the picker - returns list of (cx, cy) tuples
            points = pick_points_gui(self.image_path, max_points=4)

            if points and len(points) == 4:
                # Format as string: "(cx1,cy1),(cx2,cy2),(cx3,cy3),(cx4,cy4)"
                coords_str = ",".join(f"({p[0]:.1f},{p[1]:.1f})" for p in points)
                self.set_coordinates(coords_str)
                self.coordinatesChanged.emit(self.image_path, coords_str)
            # If no points (user cancelled), do nothing
        except Exception as e:
            from qt_compat import QtWidgets
            QtWidgets.QMessageBox.warning(self, "Error",
                f"Failed to launch point picker:\n{str(e)}")

    def _on_browse_output(self):
        """Browse for output file."""
        from qt_compat import QtWidgets
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Select Output LYS File", "", "LYS Files (*.lys);;All Files (*.*)"
        )
        if filename:
            self.output_field.setText(filename)

    def _on_run_clicked(self):
        """Emit signal to run alignment for this image."""
        landmark_preset = self.landmark_combo.currentText()
        output_file = self.output_field.text().strip() or "auto"
        self.alignRequested.emit(self.image_path, landmark_preset, output_file)

    def _on_check_changed(self, state):
        checked_value = QtCore.Qt.Checked.value if hasattr(QtCore.Qt.Checked, 'value') else QtCore.Qt.Checked
        checked = (state == checked_value)
        self.checkStateChanged.emit(self.image_path, checked)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)

    def set_coordinates(self, coords: str):
        """Set the selected coordinates display."""
        self.selected_coordinates = coords
        self.coord_display.setText(coords)

    def get_landmark_preset(self) -> str:
        """Get the selected landmark preset name."""
        return self.landmark_combo.currentText()

    def get_output_file(self) -> str:
        """Get the output file path (or empty for auto-generated)."""
        return self.output_field.text().strip()

    def update_presets(self, presets: list):
        """Update the available landmark presets in the dropdown."""
        current = self.landmark_combo.currentText()
        self.landmark_combo.clear()
        self.landmark_combo.addItems(presets)
        if current in presets:
            self.landmark_combo.setCurrentText(current)


class PresetManagerWidget(QtWidgets.QGroupBox):
    """Widget for managing landmark presets at the bottom of the UI."""

    presetsChanged = QtCore.Signal()  # Emitted when presets are added/deleted/renamed

    def __init__(self, preset_manager: LandmarkPresetManager, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("Landmark Preset Manager", parent)
        self.preset_manager = preset_manager
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        info_label = QtWidgets.QLabel(
            "Manage GDS landmark coordinate presets. The [Default] preset uses: (-50,60),(70,60),(-50,-60),(70,-60)"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Preset list and controls
        controls_layout = QtWidgets.QHBoxLayout()

        # List of presets
        list_section = QtWidgets.QVBoxLayout()
        list_section.addWidget(QtWidgets.QLabel("Available Presets:"))

        self.preset_list = QtWidgets.QListWidget()
        self.preset_list.setMaximumHeight(120)
        self._refresh_preset_list()
        list_section.addWidget(self.preset_list)
        controls_layout.addLayout(list_section, 2)

        # Buttons
        button_section = QtWidgets.QVBoxLayout()

        self.btn_add = QtWidgets.QPushButton("Add New...")
        self.btn_add.clicked.connect(self._on_add_preset)
        button_section.addWidget(self.btn_add)

        self.btn_edit = QtWidgets.QPushButton("Edit...")
        self.btn_edit.clicked.connect(self._on_edit_preset)
        button_section.addWidget(self.btn_edit)

        self.btn_rename = QtWidgets.QPushButton("Rename...")
        self.btn_rename.clicked.connect(self._on_rename_preset)
        button_section.addWidget(self.btn_rename)

        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete_preset)
        button_section.addWidget(self.btn_delete)

        button_section.addStretch()
        controls_layout.addLayout(button_section, 1)

        layout.addLayout(controls_layout)

    def _refresh_preset_list(self):
        """Refresh the preset list display."""
        self.preset_list.clear()
        for name in self.preset_manager.get_preset_names():
            coords = self.preset_manager.get_coordinates(name)
            item_text = f"{name}: {coords}"
            self.preset_list.addItem(item_text)

    def _on_add_preset(self):
        """Add a new preset."""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Add Preset", "Enter preset name:"
        )
        if not ok or not name.strip():
            return

        coords, ok = QtWidgets.QInputDialog.getText(
            self, "Add Preset",
            f"Enter coordinates for '{name}':\n(Format: (x1,y1),(x2,y2),(x3,y3),(x4,y4))",
            text="(-50,60),(70,60),(-50,-60),(70,-60)"
        )
        if not ok or not coords.strip():
            return

        if self.preset_manager.add_preset(name.strip(), coords.strip()):
            self._refresh_preset_list()
            self.presetsChanged.emit()
            QtWidgets.QMessageBox.information(self, "Success", f"Preset '{name}' added!")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Could not add preset. Name may be invalid or already exists.")

    def _on_edit_preset(self):
        """Edit selected preset's coordinates."""
        current_item = self.preset_list.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.information(self, "Edit Preset", "Please select a preset to edit.")
            return

        # Parse name from "Name: coords" format
        item_text = current_item.text()
        name = item_text.split(":")[0].strip()

        if name == LandmarkPresetManager.DEFAULT_PRESET_NAME:
            QtWidgets.QMessageBox.warning(self, "Cannot Edit", "The default preset cannot be modified.")
            return

        current_coords = self.preset_manager.get_coordinates(name)
        coords, ok = QtWidgets.QInputDialog.getText(
            self, "Edit Preset",
            f"Edit coordinates for '{name}':",
            text=current_coords
        )
        if ok and coords.strip():
            if self.preset_manager.add_preset(name, coords.strip()):
                self._refresh_preset_list()
                self.presetsChanged.emit()
                QtWidgets.QMessageBox.information(self, "Success", f"Preset '{name}' updated!")

    def _on_rename_preset(self):
        """Rename selected preset."""
        current_item = self.preset_list.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.information(self, "Rename Preset", "Please select a preset to rename.")
            return

        item_text = current_item.text()
        old_name = item_text.split(":")[0].strip()

        if old_name == LandmarkPresetManager.DEFAULT_PRESET_NAME:
            QtWidgets.QMessageBox.warning(self, "Cannot Rename", "The default preset cannot be renamed.")
            return

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Rename Preset", f"Rename '{old_name}' to:", text=old_name
        )
        if ok and new_name.strip():
            if self.preset_manager.rename_preset(old_name, new_name.strip()):
                self._refresh_preset_list()
                self.presetsChanged.emit()
                QtWidgets.QMessageBox.information(self, "Success", f"Preset renamed to '{new_name}'!")
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Could not rename preset. Name may already exist.")

    def _on_delete_preset(self):
        """Delete selected preset."""
        current_item = self.preset_list.currentItem()
        if not current_item:
            QtWidgets.QMessageBox.information(self, "Delete Preset", "Please select a preset to delete.")
            return

        item_text = current_item.text()
        name = item_text.split(":")[0].strip()

        if name == LandmarkPresetManager.DEFAULT_PRESET_NAME:
            QtWidgets.QMessageBox.warning(self, "Cannot Delete", "The default preset cannot be deleted.")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete preset '{name}'?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            if self.preset_manager.delete_preset(name):
                self._refresh_preset_list()
                self.presetsChanged.emit()
                QtWidgets.QMessageBox.information(self, "Success", f"Preset '{name}' deleted!")


class SessionWidget(QtWidgets.QGroupBox):
    """Widget representing a single .LYS session with its images."""

    runRequested = QtCore.Signal(list)  # emits argv list for this session
    deleteRequested = QtCore.Signal(object)  # emits self when delete is requested

    def __init__(self, session_name: str, lys_path: Optional[Path], preset_manager: LandmarkPresetManager, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(session_name, parent)
        self.session_name = session_name
        self.lys_path = lys_path
        self.preset_manager = preset_manager
        self.image_strips: Dict[str, ImageStripWidget] = {}  # path -> widget

        self.setCheckable(True)
        self.setChecked(False)  # Collapsed by default

        self._build_ui()

    def _build_ui(self):
        """Build UI for this session."""
        layout = QtWidgets.QVBoxLayout(self)

        # Control row: Add button, Select All, Clear, Run Selected
        controls_row = QtWidgets.QHBoxLayout()

        self.btn_add = QtWidgets.QPushButton("Add Images...")
        self.btn_add.setToolTip("Select one or more images to align in this session")
        self.btn_add.clicked.connect(self.add_images)
        controls_row.addWidget(self.btn_add)

        self.chk_select_all = QtWidgets.QCheckBox("Select All")
        self.chk_select_all.setToolTip("Select/deselect all images in this session")
        self.chk_select_all.setEnabled(False)
        self.chk_select_all.stateChanged.connect(self._on_select_all_changed)
        controls_row.addWidget(self.chk_select_all)

        controls_row.addStretch(1)

        self.lbl_clear = QtWidgets.QLabel('<a href="#">Clear List</a>')
        self.lbl_clear.setToolTip("Remove all images from this session")
        self.lbl_clear.linkActivated.connect(self.clear_list)
        controls_row.addWidget(self.lbl_clear)

        self.btn_run_selected = QtWidgets.QPushButton("Run Selected ▶")
        self.btn_run_selected.setToolTip("Align all selected images in this session")
        self.btn_run_selected.setEnabled(False)
        self.btn_run_selected.clicked.connect(self._on_run_selected)
        controls_row.addWidget(self.btn_run_selected)

        # Add separator
        controls_row.addSpacing(16)

        # Delete session button
        self.btn_delete_session = QtWidgets.QPushButton("🗑️ Delete Session")
        self.btn_delete_session.setToolTip("Delete this entire session")
        self.btn_delete_session.setStyleSheet("color: #c00; font-weight: bold;")
        self.btn_delete_session.clicked.connect(self._on_delete_session)
        controls_row.addWidget(self.btn_delete_session)

        layout.addLayout(controls_row)

        # Scroll area for image strips
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(200)

        self.image_container = QtWidgets.QWidget()
        self.image_layout = QtWidgets.QVBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_layout.setSpacing(4)
        self.image_layout.addStretch(1)

        scroll.setWidget(self.image_container)
        layout.addWidget(scroll)

    def add_images(self):
        """Add images to this session."""
        filt = "Images (*.jpg *.jpeg *.png *.bmp *.tif *.tiff);;All files (*.*)"
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select images", "", filt)

        preset_names = self.preset_manager.get_preset_names()

        for p in paths:
            if p not in self.image_strips:
                # Create image strip widget with available presets
                strip = ImageStripWidget(p, preset_names, self.image_container)
                strip.alignRequested.connect(self._on_single_align)
                strip.checkStateChanged.connect(self._on_strip_check_changed)

                # Add to layout (before the stretch)
                self.image_layout.insertWidget(self.image_layout.count() - 1, strip)
                self.image_strips[p] = strip

        # Enable select-all and run-selected buttons if we have images
        if self.image_strips:
            self.chk_select_all.setEnabled(True)
            self.btn_run_selected.setEnabled(True)

    def clear_list(self, *_):
        """Remove all image strips from this session."""
        for strip in list(self.image_strips.values()):
            self.image_layout.removeWidget(strip)
            strip.deleteLater()
        self.image_strips.clear()
        self.chk_select_all.setChecked(False)
        self.chk_select_all.setEnabled(False)
        self.btn_run_selected.setEnabled(False)

    def _on_delete_session(self):
        """Handle delete session button click."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Session?",
            f"Are you sure you want to delete this session?\n\n{self.session_name}\n\nThis will remove the session and all its images from the interface.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self.deleteRequested.emit(self)

    def selected_images(self) -> List[str]:
        """Return only checked image paths."""
        return [path for path, strip in self.image_strips.items() if strip.is_checked()]

    def _on_select_all_changed(self, state):
        """Handle select all checkbox state change."""
        checked_value = QtCore.Qt.Checked.value if hasattr(QtCore.Qt.Checked, 'value') else QtCore.Qt.Checked
        checked = (state == checked_value)

        # Update all strip checkboxes
        for strip in self.image_strips.values():
            strip.checkStateChanged.disconnect(self._on_strip_check_changed)
            strip.set_checked(checked)
            strip.checkStateChanged.connect(self._on_strip_check_changed)

    def _on_strip_check_changed(self, path: str, checked: bool):
        """Handle individual strip checkbox change."""
        if not checked:
            self.chk_select_all.setChecked(False)
        else:
            if all(strip.is_checked() for strip in self.image_strips.values()):
                self.chk_select_all.setChecked(True)

    def _on_single_align(self, image_path: str, landmark_preset: str, output_file: str):
        """Handle individual image Run button."""
        from diagnostic_logger import get_logger
        logger = get_logger()

        # Check if coordinates have been selected
        strip = self.image_strips.get(image_path)
        if not strip or not strip.selected_coordinates:
            QtWidgets.QMessageBox.warning(
                self,
                "No Coordinates Selected",
                f"You haven't picked fiducial points for this image yet.\n\n"
                f"Please click 'Pick Points' to select 4 fiducial markers.",
                QtWidgets.QMessageBox.Ok
            )
            return

        # Get landmark coordinates from preset
        coords = self.preset_manager.get_coordinates(landmark_preset)

        # Determine output file
        if not output_file or output_file == "auto":
            if self.lys_path:
                output_file = str(self.lys_path)
            else:
                img_name = Path(image_path).stem
                output_file = str(Path.home() / "Desktop" / f"{img_name}-aligned.lys")

        # Build argv for single image
        argv = self._build_argv_for_single(image_path, coords, output_file)
        self.runRequested.emit(argv)

    def _on_run_selected(self):
        """Handle Run Selected button - batch process selected images."""
        from diagnostic_logger import get_logger
        logger = get_logger()
        selected = self.selected_images()

        if not selected:
            QtWidgets.QMessageBox.information(self, "No Selection",
                "Please select at least one image to align.")
            return

        # Check which selected images don't have coordinates picked
        missing_coords = []
        for img_path in selected:
            strip = self.image_strips.get(img_path)
            if strip and not strip.selected_coordinates:
                missing_coords.append(Path(img_path).name)

        if missing_coords:
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Missing Fiducial Points")
            msg.setText("⚠️ Some selected images don't have fiducial points picked yet!")

            detail_text = "Images missing coordinates:\n\n" + "\n".join(f"• {name}" for name in missing_coords)
            detail_text += "\n\nThese images will NOT be aligned."

            msg.setDetailedText(detail_text)
            msg.setInformativeText(f"{len(missing_coords)} of {len(selected)} selected images need fiducial points.\n\nDo you want to continue anyway?")
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
            msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)

            result = msg.exec()
            if result != QtWidgets.QMessageBox.Yes:
                return

        # Get output file for batch
        default_name = self.session_name if self.lys_path else f"Aligned-{datetime.datetime.now().strftime('%Y-%m-%d')}.lys"
        output_file, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Combined LYS File",
            str(Path.home() / "Desktop" / default_name),
            "LYS Files (*.lys);;All Files (*.*)"
        )

        if not output_file:
            return

        # Build argv for batch
        argv = self._build_argv_for_batch(selected, output_file)
        self.runRequested.emit(argv)

    def _build_argv_for_single(self, image_path: str, landmark_coords: str, output_file: str) -> list:
        """Build command arguments for single image alignment."""
        # Use picked coordinates from the strip
        strip = self.image_strips.get(image_path)
        before_coords = strip.selected_coordinates if strip else ""

        argv = [
            "--files", image_path,
            "--lys-in", "C:\\Users\\gehl2\\Auto_align_program\\Test_with_img.lys",
            "--before", before_coords,
            "--after", landmark_coords,
            "--affine",
            "--combined-out", output_file,
            "--auto-review",
            "--gds-file", "C:\\Users\\gehl2\\Auto_align_program\\Test.GDS"
        ]
        return argv

    def _build_argv_for_batch(self, image_paths: List[str], output_file: str) -> list:
        """Build command arguments for batch alignment."""
        argv = ["--files"] + image_paths
        argv.extend([
            "--lys-in", "C:\\Users\\gehl2\\Auto_align_program\\Test_with_img.lys",
            "--after", self.preset_manager.get_coordinates("[Default]"),
            "--affine",
            "--combined-out", output_file,
            "--auto-review",
            "--gds-file", "C:\\Users\\gehl2\\Auto_align_program\\Test.GDS"
        ])

        # Add before coordinates for each image
        for img_path in image_paths:
            strip = self.image_strips.get(img_path)
            if strip and strip.selected_coordinates:
                argv.extend(["--before", strip.selected_coordinates])

        return argv


class DebugWindow(QtWidgets.QDialog):
    """Separate window for debug output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verbose Debug Output")
        self.resize(900, 600)

        layout = QtWidgets.QVBoxLayout(self)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setToolTip("Alignment progress and debug output")
        layout.addWidget(self.log)

        # Clear button
        btn_clear = QtWidgets.QPushButton("Clear Log")
        btn_clear.clicked.connect(self.log.clear)
        layout.addWidget(btn_clear)


class AlignTab(QtWidgets.QWidget):
    runRequested = QtCore.Signal(list)  # emits argv list when user clicks Run

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._prefs_file = Path(__file__).parent.parent / "align_tab_prefs.json"
        self._landmarks_file = Path(__file__).parent.parent / LANDMARKS_PREFS_NAME
        self.sessions: List[SessionWidget] = []  # List of session widgets
        self._session_counter = 0  # For generating new session names
        self._debug_window: Optional[DebugWindow] = None  # Lazy-created debug window

        # Initialize preset manager
        self.preset_manager = LandmarkPresetManager(self._landmarks_file)

        self._build_ui()
        self._load_preferences()

    # ---------------- UI ----------------
    def _build_ui(self):
        """Build multi-session UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ===== SECTION 1: SESSIONS (TOP) =====
        sessions_header = QtWidgets.QHBoxLayout()
        sessions_label = QtWidgets.QLabel("<b>Sessions</b>")
        sessions_header.addWidget(sessions_label)
        sessions_header.addStretch(1)

        self.btn_new_session = QtWidgets.QPushButton("+ New Session")
        self.btn_new_session.setToolTip("Create a new alignment session")
        self.btn_new_session.clicked.connect(self._create_new_session)
        sessions_header.addWidget(self.btn_new_session)

        self.btn_open_session = QtWidgets.QPushButton("📂 Open .LYS")
        self.btn_open_session.setToolTip("Open an existing .LYS file as a new session")
        self.btn_open_session.clicked.connect(self._open_existing_session)
        sessions_header.addWidget(self.btn_open_session)

        layout.addLayout(sessions_header)

        # Sessions container (no scroll area - let page scroll instead)
        self.sessions_container = QtWidgets.QWidget()
        self.sessions_layout = QtWidgets.QVBoxLayout(self.sessions_container)
        self.sessions_layout.setContentsMargins(0, 0, 0, 0)
        self.sessions_layout.setSpacing(8)
        self.sessions_layout.addStretch(1)

        layout.addWidget(self.sessions_container)  # No stretch factor - natural height

        # ===== SECTION 2: PRESET MANAGER (BOTTOM) =====
        self.preset_widget = PresetManagerWidget(self.preset_manager, self)
        self.preset_widget.presetsChanged.connect(self._on_presets_changed)
        layout.addWidget(self.preset_widget, 1)  # Stretch factor 1

        # Create first default session
        self._create_new_session()

    def _create_new_session(self):
        """Create a new session with auto-generated name."""
        import os
        self._session_counter += 1
        username = os.getenv('USERNAME') or os.getenv('USER') or 'User'
        session_name = f"Aligned{self._session_counter}By{username}.lys"
        session = SessionWidget(session_name, None, self.preset_manager, self)

        # Wire up the session's signals
        session.runRequested.connect(self._on_session_run_requested)
        session.deleteRequested.connect(self._on_session_delete_requested)

        # Add to layout (before the stretch)
        self.sessions_layout.insertWidget(self.sessions_layout.count() - 1, session)
        self.sessions.append(session)

    def _open_existing_session(self):
        """Open an existing .LYS file as a new session."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open .LYS File", "", "KLayout Session (*.lys);;All files (*.*)"
        )
        if not path:
            return

        lys_path = Path(path)
        session_name = lys_path.name
        session = SessionWidget(session_name, lys_path, self.preset_manager, self)

        # Wire up the session's signals
        session.runRequested.connect(self._on_session_run_requested)
        session.deleteRequested.connect(self._on_session_delete_requested)

        # Add to layout (before the stretch)
        self.sessions_layout.insertWidget(self.sessions_layout.count() - 1, session)
        self.sessions.append(session)

    def _on_session_run_requested(self, argv: list):
        """Forward session run request to main window."""
        self.runRequested.emit(argv)

    def _on_session_delete_requested(self, session: SessionWidget):
        """Handle session deletion request."""
        # Remove from layout
        self.sessions_layout.removeWidget(session)

        # Remove from list
        if session in self.sessions:
            self.sessions.remove(session)

        # Delete the widget
        session.deleteLater()

    def _on_presets_changed(self):
        """Handle preset manager changes - update all sessions."""
        preset_names = self.preset_manager.get_preset_names()
        for session in self.sessions:
            for strip in session.image_strips.values():
                strip.update_presets(preset_names)

    def show_debug_window(self):
        """Show the debug window."""
        if self._debug_window is None:
            self._debug_window = DebugWindow(self)
        self._debug_window.show()
        self._debug_window.raise_()
        self._debug_window.activateWindow()

    def hide_debug_window(self):
        """Hide the debug window."""
        if self._debug_window is not None:
            self._debug_window.hide()

    # ---------- Slots for main window to hook runner feedback ----------
    @QtCore.Slot()
    def setProgressVisible(self, vis: bool):
        """Set progress bar visibility in debug window."""
        if self._debug_window is not None:
            self._debug_window.progress.setVisible(vis)

    @QtCore.Slot(int)
    def onAlignmentFinished(self, exit_code: int):
        """Called when alignment process completes."""
        # No-op in multi-session mode - sessions handle their own output
        pass

    @QtCore.Slot(str)
    def appendLog(self, text: str):
        """Append text to debug log."""
        if self._debug_window is not None:
            self._debug_window.log.append(text)

    @QtCore.Slot(str)
    def insertPlain(self, text: str):
        """Insert plain text into debug log with color coding for RMS values."""
        if self._debug_window is None:
            return

        # Check if line contains RMS error value
        if "RMS=" in text or "RMS " in text:
            # Parse RMS value
            import re
            match = re.search(r'RMS[=\s]+([\d.]+)', text)
            if match:
                try:
                    rms_value = float(match.group(1))
                    quality_indicator = self._get_quality_indicator(rms_value)
                    # Insert with color
                    self._debug_window.log.setTextColor(quality_indicator['color'])
                    self._debug_window.log.insertPlainText(text.rstrip() + f" {quality_indicator['symbol']}\n")
                    self._debug_window.log.setTextColor(QtGui.QColor("black"))  # Reset color
                    return
                except ValueError:
                    pass
        self._debug_window.log.insertPlainText(text)

    def _get_quality_indicator(self, rms_um: float) -> dict:
        """Return quality indicator based on RMS error in micrometers."""
        if rms_um < 0.3:
            return {'symbol': '✓ Excellent', 'color': QtGui.QColor('#00AA00')}  # Green
        elif rms_um < 0.5:
            return {'symbol': '✓ Good', 'color': QtGui.QColor('#88AA00')}  # Yellow-green
        elif rms_um < 1.0:
            return {'symbol': '⚠ Fair', 'color': QtGui.QColor('#FFAA00')}  # Orange
        else:
            return {'symbol': '✗ Poor', 'color': QtGui.QColor('#CC0000')}  # Red

    def set_verbose_mode(self, enabled: bool):
        """Enable or disable verbose debug mode."""
        logger = get_logger()
        logger.set_verbose(enabled)
        if enabled:
            self.appendLog(f"\n[Verbose debug mode enabled - logging to {logger.get_log_path()}]\n")
        else:
            self.appendLog("\n[Verbose debug mode disabled]\n")

    def _open_log_folder(self):
        """Open the folder containing the debug log file."""
        import subprocess
        import sys
        logger = get_logger()
        log_path = Path(logger.get_log_path())
        log_folder = log_path.parent

        try:
            if sys.platform == 'win32':
                # Windows: open folder and select the file
                subprocess.Popen(['explorer', '/select,', str(log_path)])
            elif sys.platform == 'darwin':
                # macOS: open folder
                subprocess.Popen(['open', str(log_folder)])
            else:
                # Linux: open folder
                subprocess.Popen(['xdg-open', str(log_folder)])
            logger.info(f"Opened log folder: {log_folder}")
        except Exception as e:
            logger.log_exception(e, "opening log folder")
            QtWidgets.QMessageBox.information(
                self,
                "Log File Location",
                f"Debug log file is located at:\n{log_path}"
            )

    # ---------- UI helpers ----------
    def _toggle_non_pw_panel(self, checked: bool):
        self.non_pw_frame.setVisible(checked)
        self.btn_non_pw.setText("Custom Align Markers ▲" if checked else "Custom Align Markers ▼")

    def _update_after_enabled(self, checked: bool):
        self.after_points_panel.setEnabled(bool(checked))

    def _update_output_ui(self):
        """Update UI based on selected output mode"""
        if self.radio_new_folder.isChecked():
            self.lbl_output_path.setText("Output folder:")
            self.btn_browse_folder.setVisible(True)
            self.btn_browse_lys.setVisible(False)
        else:
            self.lbl_output_path.setText("Existing .lys file:")
            self.btn_browse_folder.setVisible(False)
            self.btn_browse_lys.setVisible(True)

    def _pick_gds(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select a GDS file", "", "GDS files (*.gds *.gds2);;All files (*.*)"
        )
        if p:
            self.gds_path.setText(p)

    def add_images(self):
        filt = "Images (*.jpg *.jpeg *.png *.bmp *.tif *.tiff);;All files (*.*)"
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select images", "", filt)

        preset_names = self.preset_manager.get_preset_names()

        for p in paths:
            if p not in self.image_strips:
                # Create image strip widget with available presets
                strip = ImageStripWidget(p, preset_names, self.image_container)
                strip.alignRequested.connect(self._on_single_align)
                strip.checkStateChanged.connect(self._on_strip_check_changed)

                # Add to layout (before the stretch)
                self.image_layout.insertWidget(self.image_layout.count() - 1, strip)
                self.image_strips[p] = strip

        # Enable select-all and run-selected buttons if we have images
        if self.image_strips:
            self.chk_select_all.setEnabled(True)
            self.btn_run_selected.setEnabled(True)

    def clear_list(self, *_):
        # Remove all image strips
        for strip in list(self.image_strips.values()):
            self.image_layout.removeWidget(strip)
            strip.deleteLater()
        self.image_strips.clear()
        self.chk_select_all.setChecked(False)
        self.chk_select_all.setEnabled(False)  # Disable when no images
        self.btn_run_selected.setEnabled(False)  # Disable Run Selected too

    def choose_output_folder(self):
        # Default to parent folder of last .lys if available
        default_dir = ""
        current = self.out_path.text().strip()
        if current:
            p = Path(current)
            if p.is_file():
                default_dir = str(p.parent)
            elif p.is_dir():
                default_dir = str(p)

        p = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output folder", default_dir)
        if p:
            self.out_path.setText(p)
            self._save_preferences()

    def choose_existing_lys(self):
        # Default to parent folder of last .lys if available
        default_dir = ""
        current = self.out_path.text().strip()
        if current:
            p = Path(current)
            if p.is_file():
                default_dir = str(p.parent)
            elif p.parent.exists():
                default_dir = str(p.parent)

        p, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select existing .lys file", default_dir, "KLayout Session (*.lys);;All files (*.*)"
        )
        if p:
            self.out_path.setText(p)
            self._save_preferences()

    def current_images(self) -> List[str]:
        """Return all image paths in order."""
        return list(self.image_strips.keys())

    def selected_images(self) -> List[str]:
        """Return only checked image paths."""
        return [path for path, strip in self.image_strips.items() if strip.is_checked()]

    def _on_select_all_changed(self, state):
        """Handle select all checkbox state change."""
        from diagnostic_logger import get_logger
        logger = get_logger()

        logger.debug(f"_on_select_all_changed called with state={state}")
        logger.debug(f"Qt.Checked value = {QtCore.Qt.Checked}")
        # Compare integer values for Qt6 compatibility
        # state is an int, Qt.Checked is an enum with a .value property
        checked_value = QtCore.Qt.Checked.value if hasattr(QtCore.Qt.Checked, 'value') else QtCore.Qt.Checked
        checked = (state == checked_value)
        logger.debug(f"checked={checked} (comparing {state} == {checked_value})")
        logger.debug(f"Number of image strips: {len(self.image_strips)}")

        # Update all strip checkboxes
        # We need to temporarily disconnect their signals to prevent feedback loop
        for i, strip in enumerate(self.image_strips.values()):
            logger.debug(f"Processing strip {i+1}/{len(self.image_strips)}")
            logger.debug(f"  Before: checkbox.isChecked() = {strip.checkbox.isChecked()}")
            # Disconnect signal temporarily
            strip.checkStateChanged.disconnect(self._on_strip_check_changed)
            strip.set_checked(checked)
            logger.debug(f"  After set_checked({checked}): checkbox.isChecked() = {strip.checkbox.isChecked()}")
            # Reconnect signal
            strip.checkStateChanged.connect(self._on_strip_check_changed)

        logger.debug(f"_on_select_all_changed completed")

    def _on_strip_check_changed(self, path: str, checked: bool):
        """Handle individual strip checkbox change."""
        # Update select-all checkbox state
        if not checked:
            # If any strip is unchecked, uncheck select-all
            self.chk_select_all.setChecked(False)
        else:
            # If all strips are checked, check select-all
            if all(strip.is_checked() for strip in self.image_strips.values()):
                self.chk_select_all.setChecked(True)

    def _on_run_selected(self):
        """Handle Run Selected button - batch process selected images."""
        logger = get_logger()
        selected = self.selected_images()

        if not selected:
            QtWidgets.QMessageBox.information(self, "No Selection",
                "Please select at least one image to align.")
            return

        # Check which selected images don't have coordinates picked
        missing_coords = []
        for img_path in selected:
            strip = self.image_strips.get(img_path)
            if strip and not strip.selected_coordinates:
                missing_coords.append(Path(img_path).name)

        if missing_coords:
            # Show prominent warning
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Missing Fiducial Points")
            msg.setText("⚠️ Some selected images don't have fiducial points picked yet!")

            detail_text = "Images missing coordinates:\n\n" + "\n".join(f"• {name}" for name in missing_coords)
            detail_text += "\n\nThese images will NOT be aligned and will appear without calibration in the output .LYS file."
            detail_text += "\n\nPlease click 'Pick Points' for each image to select 4 fiducial markers before running batch alignment."

            msg.setDetailedText(detail_text)
            msg.setInformativeText(f"{len(missing_coords)} of {len(selected)} selected images need fiducial points.\n\nDo you want to continue anyway?")
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
            msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)

            result = msg.exec()
            if result != QtWidgets.QMessageBox.Yes:
                return  # User cancelled

        logger.info(f"Batch run requested for {len(selected)} selected images")

        # Get common output file for batch
        output_file, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Combined LYS File",
            str(Path.home() / "Desktop" / f"Aligned-{datetime.datetime.now().strftime('%Y-%m-%d')}.lys"),
            "LYS Files (*.lys);;All Files (*.*)"
        )

        if not output_file:
            return  # User cancelled

        # Build argv for batch - combine all selected images
        # For now, use default preset for all (TODO: per-image presets)
        argv = self._build_argv_for_batch(selected, output_file)

        # Store output file for later loading into editor
        self._last_output_file = output_file

        logger.info(f"Emitting batch run request for {len(selected)} images")
        self.runRequested.emit(argv)

    def _on_presets_changed(self):
        """Handle preset manager changes - update all strip dropdowns."""
        logger = get_logger()
        preset_names = self.preset_manager.get_preset_names()
        logger.info(f"Presets changed, updating {len(self.image_strips)} strips")

        for strip in self.image_strips.values():
            strip.update_presets(preset_names)

    def _on_single_align(self, image_path: str, landmark_preset: str, output_file: str):
        """Handle individual image Run button - align one image."""
        logger = get_logger()
        logger.info(f"Single align: {image_path}, preset={landmark_preset}, output={output_file}")

        # Get the strip to check if coordinates were picked
        strip = self.image_strips.get(image_path)
        if not strip:
            return

        # Check if coordinates have been selected
        if not strip.selected_coordinates:
            result = QtWidgets.QMessageBox.warning(
                self,
                "No Coordinates Selected",
                f"You haven't picked fiducial points for this image yet.\n\n"
                f"Image: {Path(image_path).name}\n\n"
                f"Please click 'Pick Points' to select 4 fiducial markers on the image before aligning.",
                QtWidgets.QMessageBox.Ok
            )
            return

        # Get landmark coordinates from preset
        coords = self.preset_manager.get_coordinates(landmark_preset)

        # Determine output file
        if not output_file or output_file == "auto":
            # Auto-generate output filename
            img_name = Path(image_path).stem
            output_file = str(Path.home() / "Desktop" / f"{img_name}-aligned.lys")

        # Build argv for this single image
        argv = self._build_argv_for_single(image_path, coords, output_file)

        # Store output file for later loading into editor
        self._last_output_file = output_file

        logger.info(f"Emitting single run request")
        self.runRequested.emit(argv)

    def _on_single_align_requested(self, image_path: str):
        """Handle single image align button click."""
        logger = get_logger()
        try:
            logger.info(f"Single align requested for: {image_path}")
            # Build argv for just this one image
            argv = self._build_argv_for_images([image_path])
            logger.info(f"Command arguments: {argv}")
        except Exception as e:
            logger.log_exception(e, "building command arguments for single image")
            QtWidgets.QMessageBox.critical(self, "Invalid settings", str(e))
            return
        self.setProgressVisible(True)
        self.appendLog(f"Aligning {Path(image_path).name}...\n")
        logger.info("Emitting run request signal...")
        self.runRequested.emit(argv)

    def compute_dated_lys_path(self, base: Path) -> Path:
        """Generate a unique .lys filename like Aligned-2025-10-28.lys"""
        stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        candidate = base / f"Aligned-{stamp}.lys"
        i = 2
        while candidate.exists():
            candidate = base / f"Aligned-{stamp}-{i}.lys"
            i += 1
        return candidate

    def resolve_lys(self) -> str:
        p0 = resource_path(LYS_BASENAME)
        if p0.exists(): return str(p0)
        # Fallback: return empty string if template not found - user must browse
        return ""

    def resolve_gds(self) -> str:
        p0 = resource_path(GDS_BASENAME)
        if p0.exists(): return str(p0)
        # Fallback: return empty string if template not found - user must browse
        return ""

    def _collect_after_points_str(self) -> str:
        # If Custom Align Markers panel is not open, use defaults
        if not self.btn_non_pw.isChecked():
            return DEFAULT_AFTER_POINTS

        # If custom checkbox is checked, use the spinbox values directly
        if self.chk_custom_after.isChecked():
            tl = (self.tl_x.value(), self.tl_y.value())
            tr = (self.tr_x.value(), self.tr_y.value())
            bl = (self.bl_x.value(), self.bl_y.value())
            br = (self.br_x.value(), self.br_y.value())
            def fmt(p): return f"({p[0]:.3f},{p[1]:.3f})"
            return ",".join([fmt(tl), fmt(tr), fmt(bl), fmt(br)])

        # Otherwise, use the selected preset (which already loaded into spinboxes)
        # This allows presets to work even when custom checkbox is not checked
        preset_name = self.combo_presets.currentText()
        if preset_name and preset_name != "[Default]":
            # Use values from spinboxes (already loaded by preset selection)
            tl = (self.tl_x.value(), self.tl_y.value())
            tr = (self.tr_x.value(), self.tr_y.value())
            bl = (self.bl_x.value(), self.bl_y.value())
            br = (self.br_x.value(), self.br_y.value())
            def fmt(p): return f"({p[0]:.3f},{p[1]:.3f})"
            return ",".join([fmt(tl), fmt(tr), fmt(bl), fmt(br)])

        # Fall back to default
        return DEFAULT_AFTER_POINTS

    def _build_argv_for_images(self, files: List[str]) -> list:
        """Build argv for a specific list of image files."""
        if not files:
            raise RuntimeError("No images selected.")

        out_path_str = self.out_path.text().strip()
        if not out_path_str:
            if self.radio_new_folder.isChecked():
                raise RuntimeError("Please choose an output folder.")
            else:
                raise RuntimeError("Please choose an existing .lys file.")

        # Determine the combined .lys output path
        if self.radio_new_folder.isChecked():
            # Mode 1: Create new .lys in folder
            out_folder = Path(out_path_str)
            if not out_folder.is_dir():
                raise RuntimeError(f"Output path is not a folder: {out_path_str}")
            combined_lys = self.compute_dated_lys_path(out_folder)
            lys_in = self.resolve_lys()  # Use template
        else:
            # Mode 2: Add to existing .lys
            existing_lys = Path(out_path_str)
            if not existing_lys.is_file():
                raise RuntimeError(f"Selected .lys file does not exist: {out_path_str}")
            combined_lys = existing_lys
            lys_in = str(existing_lys)  # Read from existing file

        after_str = self._collect_after_points_str()

        argv = [
            "--files", *files,
            "--lys-in", lys_in,
            "--after", after_str,
            "--affine",
            "--combined-out", str(combined_lys),
        ]
        if ALWAYS_AUTO_REVIEW:
            argv.append("--auto-review")

        gds_override = None
        if self.btn_non_pw.isChecked():
            gds_override = self.gds_path.text().strip() or None
        argv.extend(["--gds-file", gds_override or self.resolve_gds()])
        return argv

    def _build_argv_for_single(self, image_path: str, landmark_coords: str, output_file: str) -> list:
        """Build argv for a single image with specific landmark coordinates."""
        lys_in = self.resolve_lys()

        argv = [
            "--files", image_path,
            "--lys-in", lys_in,
            "--after", landmark_coords,
            "--affine",
            "--combined-out", output_file,
        ]
        if ALWAYS_AUTO_REVIEW:
            argv.append("--auto-review")

        argv.extend(["--gds-file", self.resolve_gds()])
        return argv

    def _build_argv_for_batch(self, image_paths: List[str], output_file: str) -> list:
        """Build argv for batch processing multiple images into one LYS."""
        lys_in = self.resolve_lys()

        # For now, use default preset for all images
        # TODO: Per-image preset support in batch mode
        default_coords = self.preset_manager.get_coordinates("[Default]")

        argv = [
            "--files", *image_paths,
            "--lys-in", lys_in,
            "--after", default_coords,
            "--affine",
            "--combined-out", output_file,
        ]
        if ALWAYS_AUTO_REVIEW:
            argv.append("--auto-review")

        argv.extend(["--gds-file", self.resolve_gds()])
        return argv

    def build_argv(self) -> list:
        """Build argv using selected images, or all images if none selected."""
        selected = self.selected_images()
        files = selected if selected else self.current_images()
        return self._build_argv_for_images(files)

    # Emit run
    def _emit_run(self):
        logger = get_logger()
        try:
            logger.info("Building command line arguments...")
            selected = self.selected_images()
            files = selected if selected else self.current_images()

            if not files:
                QtWidgets.QMessageBox.information(self, "No Images", "Please add images to align.")
                return

            argv = self.build_argv()
            logger.info(f"Command arguments: {argv}")

            # Show what we're processing
            if selected:
                self.appendLog(f"Processing {len(selected)} selected image(s)...\n")
            else:
                self.appendLog(f"Processing all {len(files)} image(s)...\n")

        except Exception as e:
            logger.log_exception(e, "building command arguments")
            QtWidgets.QMessageBox.critical(self, "Invalid settings", str(e));
            return
        self.setProgressVisible(True)
        self.appendLog("Launching (external Python subprocess)…\n")
        logger.info("Emitting run request signal...")
        self.runRequested.emit(argv)

    # Preferences
    def _load_preferences(self):
        """Load saved output path preference"""
        try:
            if self._prefs_file.exists():
                import json
                with open(self._prefs_file, 'r') as f:
                    prefs = json.load(f)
                    last_output = prefs.get('last_output_path', '')
                    if last_output:
                        self.out_path.setText(last_output)
        except Exception:
            pass

    def _save_preferences(self):
        """Save current output path to preferences"""
        try:
            prefs = {
                'last_output_path': self.out_path.text().strip()
            }
            with open(self._prefs_file, 'w') as f:
                json.dump(prefs, f)
        except Exception:
            pass

    # ---------- Landmark Preset Management ----------
    def _load_landmark_presets(self):
        """Load landmark presets from JSON file and populate dropdown."""
        logger = get_logger()
        try:
            # Always add [Default] option
            self.combo_presets.clear()
            self.combo_presets.addItem("[Default]")

            # Load saved presets if file exists
            if self._landmarks_file.exists():
                with open(self._landmarks_file, 'r') as f:
                    presets = json.load(f)
                    for name in sorted(presets.keys()):
                        self.combo_presets.addItem(name)

            # Update delete button state
            self._update_delete_button_state()
            logger.info(f"Loaded {self.combo_presets.count() - 1} landmark presets")
        except Exception as e:
            logger.log_exception(e, "loading landmark presets")

    def _save_landmark_presets(self, presets: Dict[str, Dict]):
        """Save landmark presets to JSON file."""
        logger = get_logger()
        try:
            with open(self._landmarks_file, 'w') as f:
                json.dump(presets, f, indent=2)
            logger.info(f"Saved {len(presets)} landmark presets")
        except Exception as e:
            logger.log_exception(e, "saving landmark presets")

    def _get_all_presets(self) -> Dict[str, Dict]:
        """Load all presets from file."""
        if not self._landmarks_file.exists():
            return {}
        try:
            with open(self._landmarks_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _on_preset_selected(self, preset_name: str):
        """Load selected preset into the spinboxes."""
        logger = get_logger()
        if not preset_name or preset_name == "[Default]":
            # Load default values
            self._load_default_landmarks()
            self._update_delete_button_state()
            return

        try:
            presets = self._get_all_presets()
            if preset_name in presets:
                coords = presets[preset_name]
                self.tl_x.setValue(coords['tl_x'])
                self.tl_y.setValue(coords['tl_y'])
                self.tr_x.setValue(coords['tr_x'])
                self.tr_y.setValue(coords['tr_y'])
                self.bl_x.setValue(coords['bl_x'])
                self.bl_y.setValue(coords['bl_y'])
                self.br_x.setValue(coords['br_x'])
                self.br_y.setValue(coords['br_y'])
                logger.info(f"Loaded preset: {preset_name}")
        except Exception as e:
            logger.log_exception(e, f"loading preset '{preset_name}'")
            QtWidgets.QMessageBox.warning(self, "Load Error", f"Failed to load preset: {str(e)}")

        self._update_delete_button_state()

    def _load_default_landmarks(self):
        """Load default landmark values into spinboxes."""
        # Parse DEFAULT_AFTER_POINTS: "(-50,60),(70,60),(-50,-60),(70,-60)"
        self.tl_x.setValue(-50)
        self.tl_y.setValue(60)
        self.tr_x.setValue(70)
        self.tr_y.setValue(60)
        self.bl_x.setValue(-50)
        self.bl_y.setValue(-60)
        self.br_x.setValue(70)
        self.br_y.setValue(-60)

    def _save_new_preset(self):
        """Save current landmark coordinates as a new preset."""
        logger = get_logger()
        preset_name = self.txt_preset_name.text().strip()

        if not preset_name:
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Please enter a name for the preset.")
            return

        if preset_name == "[Default]":
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Cannot use '[Default]' as a preset name.")
            return

        # Get current coordinates
        coords = {
            'tl_x': self.tl_x.value(),
            'tl_y': self.tl_y.value(),
            'tr_x': self.tr_x.value(),
            'tr_y': self.tr_y.value(),
            'bl_x': self.bl_x.value(),
            'bl_y': self.bl_y.value(),
            'br_x': self.br_x.value(),
            'br_y': self.br_y.value(),
        }

        # Load existing presets
        presets = self._get_all_presets()

        # Check if name already exists
        if preset_name in presets:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Overwrite Preset?",
                f"A preset named '{preset_name}' already exists. Overwrite it?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        # Save preset
        presets[preset_name] = coords
        self._save_landmark_presets(presets)

        # Reload dropdown
        current_selection = preset_name
        self._load_landmark_presets()

        # Select the newly saved preset
        index = self.combo_presets.findText(preset_name)
        if index >= 0:
            self.combo_presets.setCurrentIndex(index)

        # Clear the name field
        self.txt_preset_name.clear()

        QtWidgets.QMessageBox.information(self, "Preset Saved", f"Landmark preset '{preset_name}' saved successfully.")
        logger.info(f"Saved new preset: {preset_name}")

    def _delete_current_preset(self):
        """Delete the currently selected preset."""
        logger = get_logger()
        preset_name = self.combo_presets.currentText()

        if not preset_name or preset_name == "[Default]":
            QtWidgets.QMessageBox.information(self, "Cannot Delete", "Cannot delete the [Default] preset.")
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Preset?",
            f"Are you sure you want to delete the preset '{preset_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Load presets
            presets = self._get_all_presets()

            if preset_name in presets:
                del presets[preset_name]
                self._save_landmark_presets(presets)

                # Reload dropdown and select [Default]
                self._load_landmark_presets()
                self.combo_presets.setCurrentIndex(0)  # Select [Default]

                QtWidgets.QMessageBox.information(self, "Preset Deleted", f"Landmark preset '{preset_name}' deleted successfully.")
                logger.info(f"Deleted preset: {preset_name}")
        except Exception as e:
            logger.log_exception(e, f"deleting preset '{preset_name}'")
            QtWidgets.QMessageBox.warning(self, "Delete Error", f"Failed to delete preset: {str(e)}")

    def _update_delete_button_state(self):
        """Enable/disable delete button based on current selection."""
        current = self.combo_presets.currentText()
        self.btn_delete_preset.setEnabled(current != "[Default]" and current != "")
