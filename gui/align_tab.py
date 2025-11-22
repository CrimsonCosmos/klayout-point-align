
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
from gds_presets import GDSPresetManager

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

from functools import lru_cache
import re

@lru_cache(maxsize=8)
def resource_path(rel_path: str) -> Path:
    base = Path(getattr(__import__("sys").modules["sys"], "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel_path

def parse_coordinates(coord_str: str) -> List[Tuple[float, float]]:
    """Parse coordinate string: '(-50,60),(70,60),(-50,-60),(70,-60)'"""
    # Use regex to extract all (x,y) pairs
    pattern = r'\(([^)]+)\)'
    matches = re.findall(pattern, coord_str)
    result = []
    for match in matches:
        try:
            x, y = map(float, match.split(','))
            result.append((x, y))
        except ValueError:
            raise ValueError(f"Invalid coordinate pair: {match}")
    if len(result) != 4:
        raise ValueError(f"Expected 4 coordinates, got {len(result)}")
    return result


class ClickableLabel(QtWidgets.QLabel):
    """QLabel that emits a signal when double-clicked."""
    doubleClicked = QtCore.Signal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


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
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        # Checkbox
        self.checkbox = QtWidgets.QCheckBox()
        self.checkbox.setToolTip("Select this image for batch operations")
        self.checkbox.stateChanged.connect(self._on_check_changed)
        layout.addWidget(self.checkbox)

        # 1. Image thumbnail and name (horizontal layout)
        image_section = QtWidgets.QHBoxLayout()
        image_section.setSpacing(4)

        self.thumbnail_label = ClickableLabel()
        thumbnail = self._create_thumbnail(self.image_path, 32)
        if thumbnail:
            self.thumbnail_label.setPixmap(thumbnail)
        else:
            self.thumbnail_label.setText("[?]")
        self.thumbnail_label.setFixedSize(32, 32)
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setToolTip("Double-click to preview image")
        self.thumbnail_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.thumbnail_label.doubleClicked.connect(self._show_image_preview)
        image_section.addWidget(self.thumbnail_label)

        name_label = QtWidgets.QLabel(Path(self.image_path).name)
        name_label.setToolTip(self.image_path)
        name_label.setMaximumWidth(120)
        name_label.setWordWrap(False)
        font = name_label.font()
        font.setPointSize(8)
        name_label.setFont(font)
        image_section.addWidget(name_label)
        layout.addLayout(image_section)

        # 2. Coordinates section (compact horizontal)
        coord_section = QtWidgets.QHBoxLayout()
        coord_section.setSpacing(3)

        self.coord_display = QtWidgets.QLineEdit()
        self.coord_display.setReadOnly(True)
        self.coord_display.setPlaceholderText("No coordinates picked yet")
        self.coord_display.setMinimumWidth(200)
        self.coord_display.setMaximumHeight(24)
        self.coord_display.setToolTip("The 4 fiducial points clicked on the image")
        font = self.coord_display.font()
        font.setPointSize(8)
        self.coord_display.setFont(font)
        coord_section.addWidget(self.coord_display)
        layout.addLayout(coord_section)

        # 3. GDS Landmarks dropdown with label
        landmark_row = QtWidgets.QHBoxLayout()
        landmark_label = QtWidgets.QLabel("Landmark Preset:")
        landmark_label.setStyleSheet("font-weight: bold;")
        landmark_row.addWidget(landmark_label)

        self.landmark_combo = QtWidgets.QComboBox()
        self.landmark_combo.addItems(self.available_presets)
        self.landmark_combo.setCurrentText("[Default]")
        self.landmark_combo.setToolTip("GDS landmark preset (auto-runs when changed)")
        self.landmark_combo.setMinimumWidth(100)
        self.landmark_combo.setMaximumHeight(24)
        font = self.landmark_combo.font()
        font.setPointSize(8)
        self.landmark_combo.setFont(font)
        self.landmark_combo.currentTextChanged.connect(self._on_settings_changed)
        landmark_row.addWidget(self.landmark_combo, 1)

        landmark_row.addStretch(3)

        layout.addLayout(landmark_row)

    def _create_thumbnail(self, img_path: str, size: int = 48) -> Optional[QtGui.QPixmap]:
        """Create a thumbnail pixmap from an image file."""
        try:
            qimg = QtGui.QImage(img_path)
            if qimg.isNull():
                return None
            pixmap = QtGui.QPixmap.fromImage(qimg)
            # Use FastTransformation for thumbnails - faster and quality difference is negligible at small sizes
            return pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.FastTransformation)
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
                # Auto-run alignment after picking points
                self._auto_run_if_ready()
            # If no points (user cancelled), do nothing
        except Exception as e:
            from qt_compat import QtWidgets
            QtWidgets.QMessageBox.warning(self, "Error",
                f"Failed to launch point picker:\n{str(e)}")

    def _on_settings_changed(self):
        """Called when landmark preset changes - auto-run if ready."""
        self._auto_run_if_ready()

    def _auto_run_if_ready(self):
        """Auto-run alignment if both coordinates and landmark are set."""
        # Check if we have both coordinates and landmark preset
        if self.selected_coordinates and self.landmark_combo.currentText():
            landmark_preset = self.landmark_combo.currentText()
            output_file = "auto"  # Always auto-generate output filename
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

    def update_presets(self, presets: list):
        """Update the available landmark presets in the dropdown."""
        current = self.landmark_combo.currentText()
        self.landmark_combo.clear()
        self.landmark_combo.addItems(presets)
        if current in presets:
            self.landmark_combo.setCurrentText(current)

    def _show_image_preview(self):
        """Show a larger preview of the image in a dialog."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(Path(self.image_path).name)
        dialog.setMinimumSize(600, 600)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Load and display image
        label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(self.image_path)
        if not pixmap.isNull():
            # Scale to fit in dialog while maintaining aspect ratio
            scaled = pixmap.scaled(800, 800, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            label.setPixmap(scaled)
            label.setAlignment(QtCore.Qt.AlignCenter)
        else:
            label.setText("Failed to load image")
            label.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(label)

        # Close button
        btn_close = QtWidgets.QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()


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

        # Container for preset items
        self.preset_container = QtWidgets.QWidget()
        self.preset_layout = QtWidgets.QVBoxLayout(self.preset_container)
        self.preset_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_layout.setSpacing(2)

        # Scroll area for presets
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(self.preset_container)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(120)

        self._refresh_preset_list()
        list_section.addWidget(scroll)
        controls_layout.addLayout(list_section, 2)

        # Buttons
        button_section = QtWidgets.QVBoxLayout()

        self.btn_add = QtWidgets.QPushButton("Add New...")
        self.btn_add.clicked.connect(self._on_add_preset)
        button_section.addWidget(self.btn_add)

        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete_preset)
        button_section.addWidget(self.btn_delete)

        button_section.addStretch()
        controls_layout.addLayout(button_section, 1)

        # Reference image section (bottom right) - initially hidden
        self.reference_section = QtWidgets.QVBoxLayout()
        self.reference_section.addStretch()  # Push everything to bottom

        self.reference_label = QtWidgets.QLabel("Here are the points that correspond with the Default Landmark Preset")
        self.reference_label.setWordWrap(True)
        self.reference_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.reference_section.addWidget(self.reference_label)

        # Image display
        self.reference_image = QtWidgets.QLabel()
        self.reference_image.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.reference_image.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.reference_image.setMinimumSize(200, 150)
        self.reference_image.setMaximumSize(300, 225)
        self.reference_image.setScaledContents(True)

        # Load reference image
        reference_path = resource_path("example_points_for_manual.png")
        if reference_path.exists():
            pixmap = QtGui.QPixmap(str(reference_path))
            if not pixmap.isNull():
                self.reference_image.setPixmap(pixmap)
        else:
            self.reference_image.setText("(Reference image not found)")
            self.reference_image.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5; color: #999;")

        self.reference_section.addWidget(self.reference_image)
        controls_layout.addLayout(self.reference_section, 1)

        # Hide reference image initially
        self.reference_label.hide()
        self.reference_image.hide()
        self.reference_visible = False

        layout.addLayout(controls_layout)

    def _refresh_preset_list(self):
        """Refresh the preset list display."""
        # Clear existing items
        while self.preset_layout.count():
            child = self.preset_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add preset items
        for name in self.preset_manager.get_preset_names():
            coords = self.preset_manager.get_coordinates(name)
            item_text = f"{name}: {coords}"

            # Create row for this preset
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(5, 2, 5, 2)
            row_layout.setSpacing(5)

            # If this is the Default preset, add the help button first
            if name == self.preset_manager.DEFAULT_PRESET_NAME:
                self.btn_help = QtWidgets.QPushButton("❓")
                self.btn_help.setToolTip("Show/hide reference image for Default landmark preset")
                self.btn_help.setFixedSize(25, 25)
                self.btn_help.setStyleSheet("color: #2196F3; font-weight: bold; font-size: 14px;")
                self.btn_help.clicked.connect(self._toggle_reference_image)
                row_layout.addWidget(self.btn_help)

            # Preset label
            label = QtWidgets.QLabel(item_text)
            label.setStyleSheet("padding: 2px;")
            row_layout.addWidget(label, 1)

            self.preset_layout.addWidget(row)

        # Add stretch at the end
        self.preset_layout.addStretch()

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

        # Validate format before trying to add
        from landmark_presets import LandmarkPresetManager
        if not LandmarkPresetManager.validate_coordinates(coords.strip()):
            QtWidgets.QMessageBox.critical(
                self,
                "Invalid Format",
                "Coordinates must be in the format:\n"
                "(x1,y1),(x2,y2),(x3,y3),(x4,y4)\n\n"
                "Example: (-50,60),(70,60),(-50,-60),(70,-60)\n\n"
                "Requirements:\n"
                "• Exactly 4 coordinate pairs\n"
                "• Each pair in parentheses: (x,y)\n"
                "• Pairs separated by commas\n"
                "• Numbers can be positive/negative integers or decimals"
            )
            return

        if self.preset_manager.add_preset(name.strip(), coords.strip()):
            self._refresh_preset_list()
            self.presetsChanged.emit()
            QtWidgets.QMessageBox.information(self, "Success", f"Preset '{name}' added!")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Could not add preset. Name may be invalid or already exists.")

    def _on_delete_preset(self):
        """Delete selected preset."""
        # Get list of deletable presets (exclude default)
        all_presets = self.preset_manager.get_preset_names()
        deletable_presets = [p for p in all_presets if p != LandmarkPresetManager.DEFAULT_PRESET_NAME]

        if not deletable_presets:
            QtWidgets.QMessageBox.information(self, "Delete Preset", "No custom presets to delete.")
            return

        # Ask user to select preset to delete
        name, ok = QtWidgets.QInputDialog.getItem(
            self, "Delete Preset",
            "Select preset to delete:",
            deletable_presets,
            0, False
        )

        if not ok:
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

    def _toggle_reference_image(self):
        """Toggle visibility of the reference image and label."""
        self.reference_visible = not self.reference_visible

        if self.reference_visible:
            self.reference_label.show()
            self.reference_image.show()
        else:
            self.reference_label.hide()
            self.reference_image.hide()


class GDSPresetManagerWidget(QtWidgets.QGroupBox):
    """Widget for managing GDS file presets at the bottom of the UI."""

    presetsChanged = QtCore.Signal()  # Emitted when presets are added/deleted/renamed

    def __init__(self, gds_manager: GDSPresetManager, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("GDS File Preset Manager", parent)
        self.gds_manager = gds_manager
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        info_label = QtWidgets.QLabel(
            "Manage GDS file presets. Select different GDS layouts for alignment. The [Default - Test.GDS] preset uses the bundled Test.GDS file."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Preset list and controls
        controls_layout = QtWidgets.QHBoxLayout()

        # List of presets
        list_section = QtWidgets.QVBoxLayout()
        list_section.addWidget(QtWidgets.QLabel("Available GDS Files:"))

        # Container for preset items
        self.preset_container = QtWidgets.QWidget()
        self.preset_layout = QtWidgets.QVBoxLayout(self.preset_container)
        self.preset_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_layout.setSpacing(2)

        # Scroll area for presets
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(self.preset_container)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(120)

        self._refresh_preset_list()
        list_section.addWidget(scroll)
        controls_layout.addLayout(list_section, 2)

        # Buttons
        button_section = QtWidgets.QVBoxLayout()

        self.btn_add = QtWidgets.QPushButton("Add New...")
        self.btn_add.clicked.connect(self._on_add_preset)
        button_section.addWidget(self.btn_add)

        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete_preset)
        button_section.addWidget(self.btn_delete)

        button_section.addStretch()
        controls_layout.addLayout(button_section, 1)

        layout.addLayout(controls_layout)

    def _refresh_preset_list(self):
        """Refresh the preset list display."""
        # Clear existing items
        while self.preset_layout.count():
            child = self.preset_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add preset items
        for name in self.gds_manager.get_preset_names():
            gds_path = self.gds_manager.get_gds_path(name)
            item_text = f"{name}: {gds_path}"

            # Create row for this preset
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(5, 2, 5, 2)
            row_layout.setSpacing(5)

            # Preset label
            label = QtWidgets.QLabel(item_text)
            label.setStyleSheet("padding: 2px;")
            row_layout.addWidget(label, 1)

            # Preview button
            btn_preview = QtWidgets.QPushButton("Preview")
            btn_preview.setToolTip(f"Open {gds_path} in KLayout")
            btn_preview.setFixedWidth(80)
            btn_preview.clicked.connect(lambda checked, path=gds_path: self._on_preview_gds(path))
            row_layout.addWidget(btn_preview)

            self.preset_layout.addWidget(row)

        # Add stretch at the end
        self.preset_layout.addStretch()

    def _on_add_preset(self):
        """Add a new GDS preset."""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Add GDS Preset", "Enter preset name:"
        )
        if not ok or not name.strip():
            return

        # File dialog to select GDS file
        gds_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select GDS File",
            "",
            "GDS Files (*.gds *.GDS);;All Files (*.*)"
        )
        if not gds_path:
            return

        if self.gds_manager.add_preset(name.strip(), gds_path):
            self._refresh_preset_list()
            self.presetsChanged.emit()
            QtWidgets.QMessageBox.information(self, "Success", f"GDS preset '{name}' added!")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Could not add preset. Name may be invalid or already exists.")

    def _on_delete_preset(self):
        """Delete selected preset."""
        # Get list of deletable presets (exclude default)
        all_presets = self.gds_manager.get_preset_names()
        deletable_presets = [p for p in all_presets if p != GDSPresetManager.DEFAULT_PRESET_NAME]

        if not deletable_presets:
            QtWidgets.QMessageBox.information(self, "Delete Preset", "No custom GDS presets to delete.")
            return

        # Ask user to select preset to delete
        name, ok = QtWidgets.QInputDialog.getItem(
            self, "Delete Preset",
            "Select GDS preset to delete:",
            deletable_presets,
            0, False
        )

        if not ok:
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete GDS preset '{name}'?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            if self.gds_manager.delete_preset(name):
                self._refresh_preset_list()
                self.presetsChanged.emit()
                QtWidgets.QMessageBox.information(self, "Success", f"GDS preset '{name}' deleted!")

    def _on_preview_gds(self, gds_path: str):
        """Open GDS file in KLayout for preview."""
        import subprocess
        import sys
        from pathlib import Path

        # Resolve relative paths to absolute
        if not Path(gds_path).is_absolute():
            # Try relative to project directory
            project_root = Path(__file__).parent.parent
            full_path = project_root / gds_path
            if not full_path.exists():
                # Try relative to current working directory
                full_path = Path(gds_path).resolve()
        else:
            full_path = Path(gds_path)

        if not full_path.exists():
            QtWidgets.QMessageBox.warning(
                self, "File Not Found",
                f"GDS file not found: {gds_path}\n\nFull path tried: {full_path}"
            )
            return

        # Try to find KLayout executable
        import shutil

        klayout_candidates = [
            r"C:\Program Files\KLayout\klayout_app.exe",
            r"C:\Program Files (x86)\KLayout\klayout_app.exe",
            shutil.which("klayout_app.exe"),  # Search PATH
            shutil.which("klayout"),  # Search PATH (alternative name)
        ]

        klayout_exe = None
        for candidate in klayout_candidates:
            if candidate is None:
                continue

            # Just check if the file exists (don't run it)
            try:
                if Path(candidate).exists():
                    klayout_exe = candidate
                    break
            except:
                continue

        if not klayout_exe:
            QtWidgets.QMessageBox.warning(
                self, "KLayout Not Found",
                "Could not find KLayout installation.\n\n"
                "Please ensure KLayout is installed at:\n"
                "C:\\Program Files\\KLayout\\klayout_app.exe\n\n"
                "Or add KLayout to your system PATH."
            )
            return

        # Launch KLayout with the GDS file
        try:
            subprocess.Popen([klayout_exe, str(full_path)])
            QtWidgets.QMessageBox.information(
                self, "Preview Opened",
                f"Opening {full_path.name} in KLayout..."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to open KLayout:\n{e}"
            )


class SessionWidget(QtWidgets.QGroupBox):
    """Widget representing a single .LYS session with its images."""

    runRequested = QtCore.Signal(list)  # emits argv list for this session
    deleteRequested = QtCore.Signal(object)  # emits self when delete is requested
    closeRequested = QtCore.Signal(object)  # emits self when close is requested

    def __init__(self, session_name: str, lys_path: Optional[Path], preset_manager: LandmarkPresetManager, gds_manager: GDSPresetManager, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(session_name, parent)
        self.session_name = session_name
        self.lys_path = lys_path
        self.preset_manager = preset_manager
        self.gds_manager = gds_manager
        self.image_strips: Dict[str, ImageStripWidget] = {}  # path -> widget

        # Don't use checkable GroupBox - it disables all children when unchecked
        # Sessions are always expanded and interactive
        self.setCheckable(False)

        self._build_ui()

        # If opened from existing LYS file, load images from it
        if lys_path and lys_path.exists():
            self._load_images_from_lys()

    def _build_ui(self):
        """Build UI for this session."""
        layout = QtWidgets.QVBoxLayout(self)

        # Control row: Add button, Select All, Clear, Pick Selected
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

        self.btn_remove_selected = QtWidgets.QPushButton("Remove Selected")
        self.btn_remove_selected.setToolTip("Remove selected images from this session")
        self.btn_remove_selected.setEnabled(False)
        self.btn_remove_selected.clicked.connect(self._on_remove_selected)
        controls_row.addWidget(self.btn_remove_selected)

        self.btn_run_selected = QtWidgets.QPushButton("Pick Selected")
        self.btn_run_selected.setToolTip("Pick points for all selected images in this session")
        self.btn_run_selected.setEnabled(False)
        self.btn_run_selected.clicked.connect(self._on_run_selected)
        controls_row.addWidget(self.btn_run_selected)

        # Open in KLayout button
        self.btn_open_klayout = QtWidgets.QPushButton("📐 Open in KLayout")
        self.btn_open_klayout.setToolTip("Open this session's .lys file in KLayout")
        self.btn_open_klayout.clicked.connect(self._on_open_in_klayout)
        controls_row.addWidget(self.btn_open_klayout)

        # Add separator
        controls_row.addSpacing(16)

        # Close session button (removes from interface, keeps file)
        self.btn_close_session = QtWidgets.QPushButton("Close Session")
        self.btn_close_session.setToolTip("Close this session (removes from interface, keeps .lys file on Desktop)")
        self.btn_close_session.clicked.connect(self._on_close_session)
        controls_row.addWidget(self.btn_close_session)

        # Delete session button (removes from interface AND deletes file)
        self.btn_delete_session = QtWidgets.QPushButton("🗑️ Delete Session")
        self.btn_delete_session.setToolTip("Delete this entire session and remove .lys file from Desktop")
        self.btn_delete_session.setStyleSheet("color: #c00; font-weight: bold;")
        self.btn_delete_session.clicked.connect(self._on_delete_session)
        controls_row.addWidget(self.btn_delete_session)

        layout.addLayout(controls_row)

        # GDS selection row
        gds_row = QtWidgets.QHBoxLayout()
        gds_label = QtWidgets.QLabel("GDS File:")
        gds_label.setStyleSheet("font-weight: bold;")
        gds_row.addWidget(gds_label)

        self.gds_combo = QtWidgets.QComboBox()
        self.gds_combo.setToolTip("Select which GDS file to use for alignment in this session")
        self.gds_combo.addItems(self.gds_manager.get_preset_names())
        # Default to the first preset (which is [Default - Test.GDS])
        self.gds_combo.setCurrentIndex(0)
        self.gds_combo.currentTextChanged.connect(self._on_gds_changed)
        gds_row.addWidget(self.gds_combo, 1)

        gds_row.addStretch(3)

        layout.addLayout(gds_row)

        # Container for image strips (no scroll area - let session grow naturally)
        self.image_container = QtWidgets.QWidget()
        self.image_layout = QtWidgets.QVBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_layout.setSpacing(4)
        self.image_layout.addStretch(1)

        layout.addWidget(self.image_container)

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
            self.btn_remove_selected.setEnabled(True)

    def clear_list(self, *_):
        """Remove all image strips from this session."""
        for strip in list(self.image_strips.values()):
            self.image_layout.removeWidget(strip)
            strip.deleteLater()
        self.image_strips.clear()
        self.chk_select_all.setChecked(False)
        self.chk_select_all.setEnabled(False)
        self.btn_run_selected.setEnabled(False)
        self.btn_remove_selected.setEnabled(False)

    def _load_images_from_lys(self):
        """Load image paths from an existing LYS file."""
        if not self.lys_path or not self.lys_path.exists():
            return

        try:
            from klayout_point_align.lys_io import extract_image_paths_from_lys, extract_alignment_metadata_from_lys

            image_paths = extract_image_paths_from_lys(str(self.lys_path))
            alignment_metadata = extract_alignment_metadata_from_lys(str(self.lys_path))
            preset_names = self.preset_manager.get_preset_names()

            for img_path in image_paths:
                # Check if image file exists
                if not Path(img_path).exists():
                    print(f"Warning: Image not found: {img_path}")
                    continue

                if img_path not in self.image_strips:
                    # Create image strip widget
                    strip = ImageStripWidget(img_path, preset_names, self.image_container)
                    strip.alignRequested.connect(self._on_single_align)
                    strip.checkStateChanged.connect(self._on_strip_check_changed)

                    # If alignment metadata exists for this image, set the coordinates
                    if img_path in alignment_metadata:
                        coords_str = alignment_metadata[img_path]
                        strip.set_coordinates(coords_str)

                    # Add to layout (before the stretch)
                    self.image_layout.insertWidget(self.image_layout.count() - 1, strip)
                    self.image_strips[img_path] = strip

            # Enable controls if we loaded images
            if self.image_strips:
                self.chk_select_all.setEnabled(True)
                self.btn_run_selected.setEnabled(True)
                self.btn_remove_selected.setEnabled(True)

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Error Loading Images",
                f"Failed to load images from LYS file:\n{str(e)}"
            )

    def _on_open_in_klayout(self):
        """Open this session's .lys file in KLayout."""
        import subprocess
        import os
        import xml.etree.ElementTree as ET

        # Get the .lys file path
        if self.lys_path and self.lys_path.exists():
            lys_file = self.lys_path
        else:
            # Try Desktop location
            lys_file = Path.home() / "Desktop" / self.session_name
            if not lys_file.exists():
                QtWidgets.QMessageBox.warning(
                    self,
                    "File Not Found",
                    f"Could not find .lys file:\n{lys_file}\n\nMake sure the session has been saved."
                )
                return

        # Update the GDS file path in the .lys file before opening
        try:
            selected_gds = self.get_selected_gds_path()

            # Parse the .lys file
            tree = ET.parse(str(lys_file))
            root = tree.getroot()

            # Find and update the GDS file path
            # Look for <layout><file-path> element
            for layout_elem in root.findall('.//layout'):
                file_path_elem = layout_elem.find('file-path')
                if file_path_elem is not None:
                    file_path_elem.text = selected_gds

            # Write back to file
            tree.write(str(lys_file), encoding='utf-8', xml_declaration=True)

        except Exception as e:
            # Log the error but continue - the file might not have a GDS reference yet
            from diagnostic_logger import get_logger
            logger = get_logger()
            logger.warning(f"Could not update GDS path in .lys file: {e}")

        # Open with default application (should be KLayout if .lys is associated)
        try:
            os.startfile(str(lys_file))
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Opening File",
                f"Failed to open .lys file:\n{str(e)}\n\n"
                f"Make sure KLayout is installed and associated with .lys files."
            )

    def _on_close_session(self):
        """Handle close session button click - removes from interface but keeps file."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Close Session?",
            f"Close this session?\n\n{self.session_name}\n\nThe session will be removed from the interface, but the .lys file will remain on your Desktop.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.closeRequested.emit(self)

    def _on_delete_session(self):
        """Handle delete session button click - removes from interface AND deletes file."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Session?",
            f"Are you sure you want to delete this session?\n\n{self.session_name}\n\nThis will remove the session from the interface AND delete the .lys file from your Desktop.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.deleteRequested.emit(self)

    def _on_gds_changed(self):
        """Handle GDS dropdown change - update the .lys file with new GDS path."""
        import xml.etree.ElementTree as ET
        from diagnostic_logger import get_logger
        logger = get_logger()

        # Get the desktop path for this session
        desktop_path = Path.home() / "Desktop" / self.session_name

        # Only update if the .lys file exists
        if not desktop_path.exists():
            return

        try:
            # Get the newly selected GDS path
            selected_gds = self.get_selected_gds_path()

            # Parse the .lys file
            tree = ET.parse(str(desktop_path))
            root = tree.getroot()

            # Find and update the GDS file path
            for layout_elem in root.findall('.//layout'):
                file_path_elem = layout_elem.find('file-path')
                if file_path_elem is not None:
                    file_path_elem.text = selected_gds

            # Write back to file
            tree.write(str(desktop_path), encoding='utf-8', xml_declaration=True)
            logger.info(f"Updated GDS file in {self.session_name} to: {selected_gds}")
        except Exception as e:
            logger.log_exception(e, f"updating GDS file in {self.session_name}")

    def update_gds_presets(self, gds_preset_names: List[str]):
        """Update the GDS dropdown when presets change."""
        # Temporarily disconnect signal to avoid triggering GDS update during refresh
        self.gds_combo.currentTextChanged.disconnect(self._on_gds_changed)

        current_selection = self.gds_combo.currentText()
        self.gds_combo.clear()
        self.gds_combo.addItems(gds_preset_names)

        # Try to restore previous selection, otherwise default to first item
        index = self.gds_combo.findText(current_selection)
        if index >= 0:
            self.gds_combo.setCurrentIndex(index)
        else:
            self.gds_combo.setCurrentIndex(0)

        # Reconnect signal
        self.gds_combo.currentTextChanged.connect(self._on_gds_changed)

    def get_selected_gds_path(self) -> str:
        """Get the GDS file path for the currently selected preset."""
        from gui.runner import resource_path
        preset_name = self.gds_combo.currentText()
        gds_path = self.gds_manager.get_gds_path(preset_name)

        # Resolve to absolute path
        if not Path(gds_path).is_absolute():
            # Try as bundled resource first
            resolved = resource_path(gds_path)
            if resolved.exists():
                return str(resolved)
            # Otherwise return as-is (user might have provided absolute path)
        return gds_path

    def has_unaligned_images(self) -> bool:
        """Check if this session has any images without picked coordinates."""
        for strip in self.image_strips.values():
            if not strip.selected_coordinates:
                return True
        return False

    def count_unaligned_images(self) -> int:
        """Count how many images don't have picked coordinates."""
        return sum(1 for strip in self.image_strips.values() if not strip.selected_coordinates)

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

        # Determine output file - always use session name on Desktop
        if not output_file or output_file == "auto":
            # Always save to Desktop with session name
            output_file = str(Path.home() / "Desktop" / self.session_name)

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

        # Launch picker for selected images
        for img_path in selected:
            strip = self.image_strips.get(img_path)
            if strip:
                # Auto-launch picker for this image
                try:
                    from klayout_point_align.picker import pick_points_gui
                    logger.info(f"Launching picker for {Path(img_path).name}")

                    points = pick_points_gui(img_path, max_points=4)

                    if points and len(points) == 4:
                        # Format as string
                        coords_str = ",".join(f"({p[0]:.1f},{p[1]:.1f})" for p in points)
                        strip.set_coordinates(coords_str)
                    else:
                        # User cancelled - ask if they want to skip this image
                        reply = QtWidgets.QMessageBox.question(
                            self, "Skip Image?",
                            f"No points picked for {Path(img_path).name}.\n\nSkip this image?",
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel
                        )
                        if reply == QtWidgets.QMessageBox.Cancel:
                            return  # Cancel entire batch
                        else:
                            continue  # Skip this image
                except Exception as e:
                    logger.log_exception(e, f"launching picker for {img_path}")
                    QtWidgets.QMessageBox.warning(
                        self, "Picker Error",
                        f"Failed to launch picker for {Path(img_path).name}:\n{str(e)}"
                    )
                    return

        # Always save to Desktop with session name (no prompt)
        output_file = str(Path.home() / "Desktop" / self.session_name)

        # Since we already have the picked coordinates, call alignment function directly
        # instead of using the batch runner (which doesn't support --before)
        try:
            print(f"DEBUG: Starting alignment for {len(selected)} images")
            from klayout_point_align import align_markers, AlignConfig
            from klayout_point_align.lys_io import reset_z_counter

            # Reset z-counter for layering images in KLayout
            reset_z_counter()

            # For the first image, use the template; for subsequent images, use the output file
            current_lys_in = str(resource_path("Test_with_img.lys"))

            # Process each image with its picked coordinates
            for idx, img_path in enumerate(selected):
                strip = self.image_strips.get(img_path)
                if not strip or not strip.selected_coordinates:
                    continue  # Skip images without coordinates

                # Parse coordinates using optimized regex parser
                coords_str = strip.selected_coordinates
                picked_points = parse_coordinates(coords_str)

                # Get landmark coordinates for this image's preset
                preset = strip.get_landmark_preset()
                landmark_coords_str = self.preset_manager.get_coordinates(preset)
                target_points = parse_coordinates(landmark_coords_str)

                # Create configuration
                cfg = AlignConfig(
                    after_pts_um=target_points,
                    affine_only=True,
                    rms_thresh_um=0.5,
                    after_origin_um=(0.0, 0.0)
                )

                # Run alignment
                align_markers(
                    before_ctr_px=picked_points,
                    cfg=cfg,
                    lys_in=current_lys_in,
                    lys_out=output_file,
                    image_file=img_path,
                    gds_file=self.get_selected_gds_path()
                )

                # After first image, use the output file as input for subsequent images
                current_lys_in = output_file

            # Trigger wave animation on successful alignment
            if hasattr(self, 'wave_widget') and self.wave_widget:
                print("DEBUG: Triggering wave animation")
                self.wave_widget.trigger_alignment_animation()
            else:
                print("DEBUG: Wave widget not found or not set")

            QtWidgets.QMessageBox.information(
                self, "Alignment Complete",
                f"Successfully aligned {len(selected)} image(s).\n\nOutput: {output_file}"
            )

        except Exception as e:
            logger.log_exception(e, "running alignment")
            QtWidgets.QMessageBox.critical(
                self, "Alignment Error",
                f"Failed to run alignment:\n{str(e)}"
            )

    def _on_remove_selected(self):
        """Remove selected images from this session."""
        selected = self.selected_images()

        if not selected:
            QtWidgets.QMessageBox.information(self, "No Selection",
                "Please select at least one image to remove.")
            return

        # Confirm removal
        count = len(selected)
        plural = "image" if count == 1 else "images"
        reply = QtWidgets.QMessageBox.question(
            self, "Remove Images?",
            f"Remove {count} selected {plural} from this session?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel
        )

        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        # Remove the selected strips
        for img_path in selected:
            strip = self.image_strips.get(img_path)
            if strip:
                self.image_layout.removeWidget(strip)
                strip.deleteLater()
                del self.image_strips[img_path]

        # Update UI state
        if not self.image_strips:
            # No images left - disable all buttons
            self.chk_select_all.setChecked(False)
            self.chk_select_all.setEnabled(False)
            self.btn_run_selected.setEnabled(False)
            self.btn_remove_selected.setEnabled(False)
        else:
            # Still have images - update select all state
            self.chk_select_all.setChecked(False)

    def _build_argv_for_single(self, image_path: str, landmark_coords: str, output_file: str) -> list:
        """Build command arguments for single image alignment - includes ALL images in session."""
        # Include ALL images in the session, not just the one being aligned
        all_images = list(self.image_strips.keys())

        argv = [
            "--files"] + all_images + [
            "--lys-in", str(resource_path("Test_with_img.lys")),
            "--after", landmark_coords,
            "--affine",
            "--combined-out", output_file,
            "--auto-review",
            "--gds-file", self.get_selected_gds_path()
        ]

        # Note: --auto-review will launch the GUI picker for each image
        # The batch runner doesn't support --before arguments

        return argv

    def _build_argv_for_batch(self, image_paths: List[str], output_file: str) -> list:
        """Build command arguments for batch alignment."""

        # Determine which landmark preset to use
        # Check what presets are selected for each image
        presets_used = set()
        for img_path in image_paths:
            strip = self.image_strips.get(img_path)
            if strip:
                preset = strip.get_landmark_preset()
                presets_used.add(preset)

        # If all images use the same preset, use that. Otherwise default to [Default]
        if len(presets_used) == 1:
            chosen_preset = list(presets_used)[0]
        else:
            chosen_preset = "[Default]"

        landmark_coords = self.preset_manager.get_coordinates(chosen_preset)

        argv = ["--files"] + image_paths
        argv.extend([
            "--lys-in", str(resource_path("Test_with_img.lys")),
            "--after", landmark_coords,
            "--affine",
            "--combined-out", output_file,
            "--gds-file", self.get_selected_gds_path()
        ])

        # Note: The batch runner script doesn't support --before arguments.
        # We use --auto mode which will automatically detect fiducials on the images.
        # If automatic detection fails, it will use the --after coordinates as fallback.
        argv.append("--auto")

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

        # Initialize GDS preset manager
        self._gds_presets_file = Path(__file__).parent.parent / "gds_presets.json"
        self.gds_manager = GDSPresetManager(self._gds_presets_file)

        # Load preferences BEFORE building UI (so counter is restored before first session)
        self._load_preferences()
        self._build_ui()

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

        # ===== SECTION 2: PRESET MANAGERS (BOTTOM) =====
        self.preset_widget = PresetManagerWidget(self.preset_manager, self)
        self.preset_widget.presetsChanged.connect(self._on_presets_changed)
        layout.addWidget(self.preset_widget, 0)  # No stretch - natural size

        # GDS Preset Manager (below landmark manager)
        self.gds_widget = GDSPresetManagerWidget(self.gds_manager, self)
        self.gds_widget.presetsChanged.connect(self._on_gds_presets_changed)
        layout.addWidget(self.gds_widget, 0)  # No stretch - natural size

        # Add stretch to push preset managers to natural size
        layout.addStretch(1)

    def _create_new_session(self):
        """Create a new session with auto-generated name."""
        import getpass
        import shutil
        self._session_counter += 1

        # Get username (e.g., "Dylan", "John", etc.)
        try:
            username = getpass.getuser()
        except:
            username = "User"

        session_name = f"Aligned{self._session_counter}By{username}.lys"
        session = SessionWidget(session_name, None, self.preset_manager, self.gds_manager, self)

        # Wire up the session's signals
        session.runRequested.connect(self._on_session_run_requested)
        session.deleteRequested.connect(self._on_session_delete_requested)
        session.closeRequested.connect(self._on_session_close_requested)

        # Add to layout (before the stretch)
        self.sessions_layout.insertWidget(self.sessions_layout.count() - 1, session)
        self.sessions.append(session)

        # Save preferences to persist counter
        self._save_preferences()

        # Create empty .lys file on Desktop immediately
        desktop_path = Path.home() / "Desktop" / session_name
        template_path = Path(__file__).parent.parent / "Test_with_img.lys"
        try:
            import xml.etree.ElementTree as ET

            # Copy template to Desktop
            shutil.copy(template_path, desktop_path)

            # Update the GDS file path in the copied .lys file to match the session's selected GDS
            selected_gds = session.get_selected_gds_path()
            tree = ET.parse(str(desktop_path))
            root = tree.getroot()

            # Find and update the GDS file path
            for layout_elem in root.findall('.//layout'):
                file_path_elem = layout_elem.find('file-path')
                if file_path_elem is not None:
                    file_path_elem.text = selected_gds

            # Write back to file
            tree.write(str(desktop_path), encoding='utf-8', xml_declaration=True)
        except Exception as e:
            print(f"Warning: Could not create/update {desktop_path}: {e}")

    def _open_existing_session(self):
        """Open an existing .LYS file as a new session."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open .LYS File", "", "KLayout Session (*.lys);;All files (*.*)"
        )
        if not path:
            return

        lys_path = Path(path)
        session_name = lys_path.name
        session = SessionWidget(session_name, lys_path, self.preset_manager, self.gds_manager, self)

        # Wire up the session's signals
        session.runRequested.connect(self._on_session_run_requested)
        session.deleteRequested.connect(self._on_session_delete_requested)
        session.closeRequested.connect(self._on_session_close_requested)

        # Add to layout (before the stretch)
        self.sessions_layout.insertWidget(self.sessions_layout.count() - 1, session)
        self.sessions.append(session)

    def _on_session_run_requested(self, argv: list):
        """Forward session run request to main window."""
        self.runRequested.emit(argv)

    def _on_session_close_requested(self, session: SessionWidget):
        """Handle session close request - remove from interface, keep file."""
        # Remove from layout
        self.sessions_layout.removeWidget(session)

        # Remove from list
        if session in self.sessions:
            self.sessions.remove(session)

        # Delete the widget
        session.deleteLater()

    def _on_session_delete_requested(self, session: SessionWidget):
        """Handle session deletion request - remove from interface AND delete file."""
        # Delete .lys file from Desktop
        desktop_path = Path.home() / "Desktop" / session.session_name
        try:
            if desktop_path.exists():
                desktop_path.unlink()
        except Exception as e:
            print(f"Warning: Could not delete {desktop_path}: {e}")

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

    def _on_gds_presets_changed(self):
        """Handle GDS preset manager changes - update all sessions."""
        gds_preset_names = self.gds_manager.get_preset_names()
        for session in self.sessions:
            session.update_gds_presets(gds_preset_names)

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
            self.btn_remove_selected.setEnabled(True)

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
        """Load saved session counter"""
        try:
            if self._prefs_file.exists():
                import json
                with open(self._prefs_file, 'r') as f:
                    prefs = json.load(f)
                    # Load session counter to persist across app restarts
                    self._session_counter = prefs.get('session_counter', 0)
        except Exception:
            pass

    def _save_preferences(self):
        """Save session counter to preferences"""
        try:
            import json
            prefs = {
                'session_counter': self._session_counter
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

    def has_unaligned_images(self) -> bool:
        """Check if any session has unaligned images."""
        for session in self.sessions:
            if session.has_unaligned_images():
                return True
        return False

    def get_unaligned_summary(self) -> str:
        """Get a summary of unaligned images across all sessions."""
        unaligned_sessions = []
        for session in self.sessions:
            count = session.count_unaligned_images()
            if count > 0:
                unaligned_sessions.append((session.session_name, count))

        if not unaligned_sessions:
            return ""

        lines = ["The following sessions have unaligned images:\n"]
        for session_name, count in unaligned_sessions:
            plural = "image" if count == 1 else "images"
            lines.append(f"  • {session_name}: {count} {plural} without coordinates")

        return "\n".join(lines)
