
# gui/align_tab.py
# Self-contained AlignTab widget that builds argv and exposes log/progress hooks.

from __future__ import annotations
import datetime
from pathlib import Path
from typing import List, Optional

from qt_compat import QtCore, QtGui, QtWidgets
from diagnostic_logger import get_logger

# ---- Constants mirrored from the legacy main ----
APP_TITLE = "Point Align v1.1"
COMBINED_FILENAME = "session_combined.lys"
PREFS_NAME = "align_gui_prefs.json"

# Template .lys shipped with the app
LYS_BASENAME = "Test_with_img.lys"

# Canonical GDS for PW Group users (ship alongside app)
GDS_BASENAME = "Test.GDS"

DEFAULT_AFTER_POINTS = "(-50,60),(70,60),(-50,-60),(70,-60)"  # TL, TR, BL, BR (µm)
ALWAYS_AUTO_REVIEW = True

def resource_path(rel_path: str) -> Path:
    base = Path(getattr(__import__("sys").modules["sys"], "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel_path

class AlignTab(QtWidgets.QWidget):
    runRequested = QtCore.Signal(list)  # emits argv list when user clicks Run

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._prefs_file = Path(__file__).parent.parent / "align_tab_prefs.json"
        self._build_ui()
        self._load_preferences()

    # ---------------- UI ----------------
    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        panel = QtWidgets.QFrame()
        v.addWidget(panel, 1)
        grid = QtWidgets.QGridLayout(panel)

        # Input images
        grp_in = QtWidgets.QGroupBox("Input Images")
        grid.addWidget(grp_in, 0, 0, 1, 2)
        g1 = QtWidgets.QVBoxLayout(grp_in)
        row = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add images…")
        self.btn_add.setToolTip("Select one or more images to align (JPG, PNG, TIF, etc.)")
        self.btn_add.clicked.connect(self.add_images)
        row.addWidget(self.btn_add)
        row.addStretch(1)
        self.lbl_clear = QtWidgets.QLabel('<a href="#">Clear list</a>')
        self.lbl_clear.setToolTip("Remove all images from the list")
        self.lbl_clear.linkActivated.connect(self.clear_list)
        row.addWidget(self.lbl_clear)
        g1.addLayout(row)
        self.list = QtWidgets.QListWidget()
        self.list.setIconSize(QtCore.QSize(64, 64))  # Set thumbnail size
        self.list.setSpacing(2)  # Add spacing between items
        self.list.setToolTip("Images to be aligned. Hover over each to see the full path.")
        g1.addWidget(self.list)

        # Output
        grp_out = QtWidgets.QGroupBox("Output")
        grid.addWidget(grp_out, 1, 0, 1, 2)
        g2 = QtWidgets.QVBoxLayout(grp_out)

        # Output mode radio buttons
        radio_row = QtWidgets.QHBoxLayout()
        self.radio_new_folder = QtWidgets.QRadioButton("Create new .lys in folder")
        self.radio_new_folder.setToolTip("Create a new .lys file with dated name (e.g., Aligned-2025-10-28.lys)")
        self.radio_existing_lys = QtWidgets.QRadioButton("Add to existing .lys file")
        self.radio_existing_lys.setToolTip("Append aligned images to an existing .lys session file")
        self.radio_new_folder.setChecked(True)
        self.radio_new_folder.toggled.connect(self._update_output_ui)
        radio_row.addWidget(self.radio_new_folder)
        radio_row.addWidget(self.radio_existing_lys)
        radio_row.addStretch(1)
        g2.addLayout(radio_row)

        # Output path selector
        path_row = QtWidgets.QHBoxLayout()
        self.lbl_output_path = QtWidgets.QLabel("Output folder:")
        self.out_path = QtWidgets.QLineEdit()
        self.out_path.setToolTip("Path where the .lys file will be created/updated")
        self.btn_browse_folder = QtWidgets.QPushButton("Browse Folder…")
        self.btn_browse_folder.setToolTip("Choose a folder to save new .lys files")
        self.btn_browse_lys = QtWidgets.QPushButton("Browse .lys…")
        self.btn_browse_lys.setToolTip("Select an existing .lys file to add images to")
        self.btn_browse_folder.clicked.connect(self.choose_output_folder)
        self.btn_browse_lys.clicked.connect(self.choose_existing_lys)
        path_row.addWidget(self.lbl_output_path)
        path_row.addWidget(self.out_path, 1)
        path_row.addWidget(self.btn_browse_folder)
        path_row.addWidget(self.btn_browse_lys)
        g2.addLayout(path_row)

        self._update_output_ui()

        # Run
        grp_run = QtWidgets.QGroupBox("Run")
        grid.addWidget(grp_run, 2, 0, 1, 2)
        g3 = QtWidgets.QVBoxLayout(grp_run)

        # Run button and verbose debug checkbox
        run_row = QtWidgets.QHBoxLayout()
        self.btn_run = QtWidgets.QPushButton("Run")
        self.btn_run.setToolTip("Start the alignment process (Ctrl+Enter)")
        self.btn_run.setShortcut("Ctrl+Return")
        self.btn_run.clicked.connect(self._emit_run)
        run_row.addWidget(self.btn_run)

        self.chk_verbose = QtWidgets.QCheckBox("Verbose Debug Mode")
        self.chk_verbose.setToolTip("Enable detailed diagnostic logging to help troubleshoot issues.\nLog file saved to: PointAlign_debug.log")
        self.chk_verbose.toggled.connect(self._on_verbose_toggled)
        run_row.addWidget(self.chk_verbose)

        self.btn_open_log = QtWidgets.QPushButton("Open Log Folder")
        self.btn_open_log.setToolTip("Open the folder containing the debug log file")
        self.btn_open_log.clicked.connect(self._open_log_folder)
        run_row.addWidget(self.btn_open_log)

        run_row.addStretch(1)

        g3.addLayout(run_row)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setToolTip("Alignment in progress...")
        g3.addWidget(self.progress)
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setToolTip("Alignment output log. Shows RMS error with quality indicators (✓ Excellent, ✓ Good, ⚠ Fair, ✗ Poor)")
        g3.addWidget(self.log)

        # Non-PW Group collapsible
        self.btn_non_pw = QtWidgets.QPushButton("Custom Align Markers ▼")
        self.btn_non_pw.setCheckable(True)
        self.btn_non_pw.setToolTip("Show options for custom alignment marker coordinates")
        self.btn_non_pw.clicked.connect(self._toggle_non_pw_panel)

        self.non_pw_frame = QtWidgets.QFrame()
        self.non_pw_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.non_pw_frame.setVisible(False)

        non_pw_layout = QtWidgets.QFormLayout(self.non_pw_frame)
        non_pw_layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        non_pw_layout.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        non_pw_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        non_pw_layout.setHorizontalSpacing(8)
        non_pw_layout.setVerticalSpacing(6)
        non_pw_layout.setContentsMargins(6, 6, 6, 6)

        # Row: custom .gds file
        row_gds = QtWidgets.QHBoxLayout()
        row_gds.setSpacing(6)
        row_gds.setContentsMargins(0, 0, 0, 0)
        self.gds_path = QtWidgets.QLineEdit()
        self.gds_path.setPlaceholderText("Choose a .gds to embed into the .lys for this run…")
        self.gds_path.setToolTip("GDS layout file to use instead of the default Test.GDS")
        btn_pick_gds = QtWidgets.QPushButton("Browse…")
        btn_pick_gds.setToolTip("Select a custom GDS/GDSII layout file")
        btn_pick_gds.clicked.connect(self._pick_gds)
        row_gds.addWidget(self.gds_path, 1)
        row_gds.addWidget(btn_pick_gds, 0)
        non_pw_layout.addRow("Custom GDS file:", row_gds)

        # Row: custom landmarker points (µm)
        self.chk_custom_after = QtWidgets.QCheckBox("Custom landmarker points (µm)")
        self.chk_custom_after.setToolTip("Enable this to specify custom fiducial marker positions instead of using defaults")
        self.chk_custom_after.toggled.connect(self._update_after_enabled)
        non_pw_layout.addRow(self.chk_custom_after)

        # TL/TR/BL/BR grid
        grid_after = QtWidgets.QGridLayout()
        grid_after.setHorizontalSpacing(8)
        grid_after.setVerticalSpacing(4)
        grid_after.setContentsMargins(0, 0, 0, 0)

        def mkspin(default):
            sb = QtWidgets.QDoubleSpinBox()
            sb.setRange(-100000.0, 100000.0)
            sb.setDecimals(3)
            sb.setSingleStep(1.0)
            sb.setValue(float(default))
            sb.setMaximumWidth(120)
            return sb

        def mklabel(txt: str) -> QtWidgets.QLabel:
            L = QtWidgets.QLabel(txt)
            L.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            L.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)
            L.setMinimumWidth(36)
            L.setStyleSheet("font-weight:600;")
            return L

        self.tl_x = mkspin(-50); self.tl_y = mkspin(60)
        self.tr_x = mkspin(70);  self.tr_y = mkspin(60)
        self.bl_x = mkspin(-50); self.bl_y = mkspin(-60)
        self.br_x = mkspin(70);  self.br_y = mkspin(-60)

        # Add tooltips to fiducial coordinates
        self.tl_x.setToolTip("Top-Left X coordinate (micrometers)")
        self.tl_y.setToolTip("Top-Left Y coordinate (micrometers)")
        self.tr_x.setToolTip("Top-Right X coordinate (micrometers)")
        self.tr_y.setToolTip("Top-Right Y coordinate (micrometers)")
        self.bl_x.setToolTip("Bottom-Left X coordinate (micrometers)")
        self.bl_y.setToolTip("Bottom-Left Y coordinate (micrometers)")
        self.br_x.setToolTip("Bottom-Right X coordinate (micrometers)")
        self.br_y.setToolTip("Bottom-Right Y coordinate (micrometers)")

        grid_after.addWidget(mklabel("TL x"), 0, 0); grid_after.addWidget(self.tl_x, 0, 1)
        grid_after.addWidget(mklabel("TL y"), 0, 2); grid_after.addWidget(self.tl_y, 0, 3)
        grid_after.addWidget(mklabel("TR x"), 1, 0); grid_after.addWidget(self.tr_x, 1, 1)
        grid_after.addWidget(mklabel("TR y"), 1, 2); grid_after.addWidget(self.tr_y, 1, 3)
        grid_after.addWidget(mklabel("BL x"), 2, 0); grid_after.addWidget(self.bl_x, 2, 1)
        grid_after.addWidget(mklabel("BL y"), 2, 2); grid_after.addWidget(self.bl_y, 2, 3)
        grid_after.addWidget(mklabel("BR x"), 3, 0); grid_after.addWidget(self.br_x, 3, 1)
        grid_after.addWidget(mklabel("BR y"), 3, 2); grid_after.addWidget(self.br_y, 3, 3)

        grid_after.setColumnStretch(1, 1); grid_after.setColumnStretch(3, 1)

        self.after_points_panel = QtWidgets.QWidget()
        self.after_points_panel.setLayout(grid_after)
        non_pw_layout.addRow(self.after_points_panel)

        self._update_after_enabled(False)

        # Add to main
        grid.addWidget(self.btn_non_pw, 3, 0, 1, 2)
        grid.addWidget(self.non_pw_frame, 4, 0, 1, 2)

    # ---------- Slots for main window to hook runner feedback ----------
    @QtCore.Slot()
    def setProgressVisible(self, vis: bool):
        self.progress.setVisible(vis)

    @QtCore.Slot(str)
    def appendLog(self, text: str):
        self.log.append(text)

    @QtCore.Slot(str)
    def insertPlain(self, text: str):
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
                    self.log.setTextColor(quality_indicator['color'])
                    self.log.insertPlainText(text.rstrip() + f" {quality_indicator['symbol']}\n")
                    self.log.setTextColor(QtGui.QColor("black"))  # Reset color
                    return
                except ValueError:
                    pass
        self.log.insertPlainText(text)

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

    def _on_verbose_toggled(self, checked: bool):
        """Handle verbose debug mode toggle."""
        logger = get_logger()
        logger.set_verbose(checked)
        if checked:
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
        for p in paths:
            if not any(self.list.item(i).text() == p for i in range(self.list.count())):
                item = QtWidgets.QListWidgetItem(Path(p).name)
                item.setToolTip(p)  # Full path in tooltip
                item.setData(QtCore.Qt.UserRole, p)  # Store full path

                # Create thumbnail
                thumbnail = self._create_thumbnail(p)
                if thumbnail:
                    item.setIcon(QtGui.QIcon(thumbnail))

                self.list.addItem(item)

    def clear_list(self, *_):
        self.list.clear()

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
        return [self.list.item(i).data(QtCore.Qt.UserRole) for i in range(self.list.count())]

    def _create_thumbnail(self, img_path: str, size: int = 64) -> Optional[QtGui.QPixmap]:
        """Create a thumbnail pixmap from an image file."""
        try:
            qimg = QtGui.QImage(img_path)
            if qimg.isNull():
                return None
            # Scale to thumbnail size while maintaining aspect ratio
            pixmap = QtGui.QPixmap.fromImage(qimg)
            return pixmap.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        except Exception:
            return None

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
        if not self.btn_non_pw.isChecked() or not self.chk_custom_after.isChecked():
            return DEFAULT_AFTER_POINTS
        tl = (self.tl_x.value(), self.tl_y.value())
        tr = (self.tr_x.value(), self.tr_y.value())
        bl = (self.bl_x.value(), self.bl_y.value())
        br = (self.br_x.value(), self.br_y.value())
        def fmt(p): return f"({p[0]:.3f},{p[1]:.3f})"
        return ",".join([fmt(tl), fmt(tr), fmt(bl), fmt(br)])

    def build_argv(self) -> list:
        files = self.current_images()
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

    # Emit run
    def _emit_run(self):
        logger = get_logger()
        try:
            logger.info("Building command line arguments...")
            argv = self.build_argv()
            logger.info(f"Command arguments: {argv}")
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
            import json
            prefs = {
                'last_output_path': self.out_path.text().strip()
            }
            with open(self._prefs_file, 'w') as f:
                json.dump(prefs, f)
        except Exception:
            pass
