
# gui/align_tab.py
# Self-contained AlignTab widget that builds argv and exposes log/progress hooks.

from __future__ import annotations
import datetime
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtWidgets

# ---- Constants mirrored from the legacy main ----
APP_TITLE = "Point Align"
COMBINED_FILENAME = "session_combined.lys"
PREFS_NAME = "align_gui_prefs.json"

# Template .lys shipped with the app (or fallback path)
LYS_BASENAME = "Test_with_img.lys"
ABSOLUTE_LYS_FALLBACK = Path(r"C:\Users\gehl2\Test_with_img.lys")

# Canonical GDS for PW Group users (ship alongside app or use absolute fallback)
GDS_BASENAME = "Test.GDS"
ABSOLUTE_GDS_FALLBACK = Path(r"C:\Users\gehl2\Test.GDS")

DEFAULT_AFTER_POINTS = "(-50,60),(70,60),(-50,-60),(70,-60)"  # TL, TR, BL, BR (µm)
ALWAYS_AUTO_REVIEW = True

def resource_path(rel_path: str) -> Path:
    base = Path(getattr(__import__("sys").modules["sys"], "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel_path

class AlignTab(QtWidgets.QWidget):
    runRequested = QtCore.Signal(list)  # emits argv list when user clicks Run

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build_ui()

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
        self.btn_add.clicked.connect(self.add_images)
        row.addWidget(self.btn_add)
        row.addStretch(1)
        self.lbl_clear = QtWidgets.QLabel('<a href="#">Clear list</a>')
        self.lbl_clear.linkActivated.connect(self.clear_list)
        row.addWidget(self.lbl_clear)
        g1.addLayout(row)
        self.list = QtWidgets.QListWidget()
        g1.addWidget(self.list)

        # Output
        grp_out = QtWidgets.QGroupBox("Output")
        grid.addWidget(grp_out, 1, 0, 1, 2)
        g2 = QtWidgets.QHBoxLayout(grp_out)
        self.out_base = QtWidgets.QLineEdit()
        self.btn_browse = QtWidgets.QPushButton("Browse…")
        self.btn_browse.clicked.connect(self.choose_out_base)
        g2.addWidget(QtWidgets.QLabel("Output base folder:"))
        g2.addWidget(self.out_base, 1)
        g2.addWidget(self.btn_browse)

        # Run
        grp_run = QtWidgets.QGroupBox("Run")
        grid.addWidget(grp_run, 2, 0, 1, 2)
        g3 = QtWidgets.QVBoxLayout(grp_run)
        self.btn_run = QtWidgets.QPushButton("Run")
        self.btn_run.clicked.connect(self._emit_run)
        g3.addWidget(self.btn_run)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        g3.addWidget(self.progress)
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        g3.addWidget(self.log)

        # Non-PW Group collapsible
        self.btn_non_pw = QtWidgets.QPushButton("Non-Pengjie Wang Group Users ▼")
        self.btn_non_pw.setCheckable(True)
        self.btn_non_pw.setToolTip("Show options for users outside the Pengjie Wang group")
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
        btn_pick_gds = QtWidgets.QPushButton("Browse…")
        btn_pick_gds.clicked.connect(self._pick_gds)
        row_gds.addWidget(self.gds_path, 1)
        row_gds.addWidget(btn_pick_gds, 0)
        non_pw_layout.addRow("Custom GDS file:", row_gds)

        # Row: custom landmarker points (µm)
        self.chk_custom_after = QtWidgets.QCheckBox("Custom landmarker points (µm)")
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
        self.log.insertPlainText(text)

    # ---------- UI helpers ----------
    def _toggle_non_pw_panel(self, checked: bool):
        self.non_pw_frame.setVisible(checked)
        self.btn_non_pw.setText("Non-Pengjie Wang Group Users ▲" if checked else "Non-Pengjie Wang Group Users ▼")

    def _update_after_enabled(self, checked: bool):
        self.after_points_panel.setEnabled(bool(checked))

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
                self.list.addItem(p)

    def clear_list(self, *_): 
        self.list.clear()

    def choose_out_base(self):
        p = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output base")
        if p: 
            self.out_base.setText(p)

    def current_images(self) -> List[str]: 
        return [self.list.item(i).text() for i in range(self.list.count())]

    def compute_dated_folder(self, base: Path) -> Path:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        candidate = base / f"Aligned-{stamp}"; i = 2
        while candidate.exists():
            candidate = base / f"Aligned-{stamp}-{i}"; i += 1
        return candidate

    def resolve_lys(self) -> str:
        p0 = resource_path(LYS_BASENAME)
        if p0.exists(): return str(p0)
        return str(ABSOLUTE_LYS_FALLBACK)

    def resolve_gds(self) -> str:
        p0 = resource_path(GDS_BASENAME)
        if p0.exists(): return str(p0)
        return str(ABSOLUTE_GDS_FALLBACK)

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
        out_base = self.out_base.text().strip()
        if not out_base: 
            raise RuntimeError("Please choose an output base folder.")
        dated = self.compute_dated_folder(Path(out_base)); dated.mkdir(parents=True, exist_ok=True)

        after_str = self._collect_after_points_str()

        argv = [
            "--files", *files,
            "--lys-in", self.resolve_lys(),
            "--after", after_str,
            "--affine",
            "--out-dir", str(dated),
            "--combined-out", str(dated / COMBINED_FILENAME),
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
        try:
            argv = self.build_argv()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Invalid settings", str(e)); 
            return
        self.setProgressVisible(True)
        self.appendLog("Launching (external Python subprocess)…\n")
        self.runRequested.emit(argv)
