# align_gui_aqua_qt.py — Aqua-styled GUI (PySide6/Qt)
# Runs the batch alignment in an external Python subprocess.
#
# Build hint:
# pyinstaller --onefile --noconsole --name PointAlign --icon icon.ico ^
#   --hidden-import point_align_batch_runner_gui --hidden-import klayout_point_align ^
#   --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 ^
#   --add-data "Test_with_img.lys;." --add-data "Test.GDS;." --add-data "point_align_batch_runner_gui.py;." ^
#   align_gui_aqua_qt.py

import os, sys, datetime, subprocess
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets

APP_TITLE = "Point Align"
COMBINED_FILENAME = "session_combined.lys"
PREFS_NAME = "align_gui_prefs.json"

# Template .lys shipped with the app (or fallback path)
LYS_BASENAME = "Test_with_img.lys"
ABSOLUTE_LYS_FALLBACK = Path(r"C:\Users\gehl2\Test_with_img.lys")

# NEW: Canonical GDS for PW Group users (ship alongside app or use absolute fallback)
GDS_BASENAME = "Test.GDS"
ABSOLUTE_GDS_FALLBACK = Path(r"C:\Users\gehl2\Test.GDS")  # <-- change if needed

DEFAULT_AFTER_POINTS = "(-50,60),(70,60),(-50,-60),(70,-60)"  # TL, TR, BL, BR (µm)
ALWAYS_AUTO_REVIEW = True

def resource_path(rel_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel_path

# ---------- External runner (only mode) ----------
class ExternalRunner(QtCore.QThread):
    line_ready = QtCore.Signal(str)
    finished_with_code = QtCore.Signal(int)
    started_with_cmd = QtCore.Signal(str)
    logfile_ready = QtCore.Signal(str)

    def __init__(self, argv_list, parent=None):
        super().__init__(parent)
        self.argv_list = argv_list

    def run(self):
        # Use bundled runner script
        script_path = resource_path("point_align_batch_runner_gui.py")
        if not script_path.exists():
            self.line_ready.emit("[ERROR] Bundled runner script not found. Rebuild with --add-data \"point_align_batch_runner_gui.py;.\".\n")
            self.finished_with_code.emit(1)
            return

        # Prepare log file
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(os.getenv("TEMP", str(Path.home()))) / f"PointAlign_run_{ts}.log"
        self.logfile_ready.emit(str(log_path))

        # Prefer system Python; fall back to 'python'
        cmd = None
        for cand in (["py", "-3"], ["py"], ["python3"], ["python"]):
            try:
                subprocess.check_output(cand + ["--version"], stderr=subprocess.STDOUT, text=True, timeout=3)
                cmd = cand + ["-u", str(script_path), *self.argv_list]
                break
            except Exception:
                continue
        if cmd is None:
            self.line_ready.emit("[ERROR] No system Python found on PATH.\n")
            self.finished_with_code.emit(1)
            return

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        pretty_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        self.started_with_cmd.emit(pretty_cmd + "\n")

        try:
            with open(log_path, "w", encoding="utf-8", errors="replace") as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    creationflags=0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW on Windows
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    lf.write(line); lf.flush()
                    self.line_ready.emit(line)
                rc = proc.wait()
        except Exception as e:
            self.line_ready.emit(f"[ERROR] Failed to start external Python: {e}\n")
            self.finished_with_code.emit(1)
            return

        self.finished_with_code.emit(rc)

# ---------- UI ----------
class AquaHeader(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setFixedHeight(56)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        rect = self.rect()
        grad = QtGui.QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, QtGui.QColor("#eaf2ff"))
        grad.setColorAt(0.5, QtGui.QColor("#d9e6ff"))
        grad.setColorAt(1.0, QtGui.QColor("#cddcff"))
        p.fillRect(rect, grad)
        pen = QtGui.QPen(QtGui.QColor("#2a2a2a"))
        p.setPen(pen)
        font = QtGui.QFont("Lucida Grande", 13)
        if "Lucida Grande" not in QtGui.QFontDatabase().families():
            font = QtGui.QFont("Segoe UI Semibold", 12)
        p.setFont(font)
        p.drawText(QtCore.QRect(16, 0, rect.width()-32, rect.height()),
                   QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
                   self.title)

class MainWin(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1000, 820)

        central = QtWidgets.QWidget(); self.setCentralWidget(central)
        v = QtWidgets.QVBoxLayout(central); v.setContentsMargins(10,8,10,10); v.setSpacing(8)

        self.header = AquaHeader("Point Align"); v.addWidget(self.header)

        panel = QtWidgets.QFrame(); v.addWidget(panel, 1); grid = QtWidgets.QGridLayout(panel)

        # Input images
        grp_in = QtWidgets.QGroupBox("Input Images"); grid.addWidget(grp_in, 0,0,1,2)
        g1 = QtWidgets.QVBoxLayout(grp_in)
        row = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add images…"); self.btn_add.clicked.connect(self.add_images)
        row.addWidget(self.btn_add); row.addStretch(1)
        self.lbl_clear = QtWidgets.QLabel('<a href="#">Clear list</a>'); self.lbl_clear.linkActivated.connect(self.clear_list)
        row.addWidget(self.lbl_clear); g1.addLayout(row)
        self.list = QtWidgets.QListWidget(); g1.addWidget(self.list)

        # Output
        grp_out = QtWidgets.QGroupBox("Output"); grid.addWidget(grp_out, 1,0,1,2)
        g2 = QtWidgets.QHBoxLayout(grp_out)
        self.out_base = QtWidgets.QLineEdit()
        self.btn_browse = QtWidgets.QPushButton("Browse…"); self.btn_browse.clicked.connect(self.choose_out_base)
        g2.addWidget(QtWidgets.QLabel("Output base folder:")); g2.addWidget(self.out_base,1); g2.addWidget(self.btn_browse)

        # Run
        grp_run = QtWidgets.QGroupBox("Run"); grid.addWidget(grp_run, 2,0,1,2)
        g3 = QtWidgets.QVBoxLayout(grp_run)
        self.btn_run = QtWidgets.QPushButton("Run"); self.btn_run.clicked.connect(self.run_clicked)
        g3.addWidget(self.btn_run)
        self.progress = QtWidgets.QProgressBar(); self.progress.setRange(0,0); self.progress.setVisible(False); g3.addWidget(self.progress)
        self.log = QtWidgets.QTextEdit(); self.log.setReadOnly(True); g3.addWidget(self.log)

        # --- Non-Pengjie Wang Group Users (collapsible) ---
        self.btn_non_pw = QtWidgets.QPushButton("Non-Pengjie Wang Group Users ▼")
        self.btn_non_pw.setCheckable(True)
        self.btn_non_pw.setToolTip("Show options for users outside the Pengjie Wang group")
        self.btn_non_pw.clicked.connect(self._toggle_non_pw_panel)

        self.non_pw_frame = QtWidgets.QFrame()
        self.non_pw_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.non_pw_frame.setVisible(False)

        non_pw_layout = QtWidgets.QFormLayout(self.non_pw_frame)
        non_pw_layout.setLabelAlignment(QtCore.Qt.AlignLeft)
        non_pw_layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # Row: custom .gds file
        row_gds = QtWidgets.QHBoxLayout()
        self.gds_path = QtWidgets.QLineEdit()
        self.gds_path.setPlaceholderText("Choose a .gds to embed into the .lys for this run…")
        btn_pick_gds = QtWidgets.QPushButton("Browse…")
        def _pick_gds():
            p, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select a GDS file", "", "GDS files (*.gds *.gds2);;All files (*.*)"
            )
            if p:
                self.gds_path.setText(p)
        btn_pick_gds.clicked.connect(_pick_gds)
        row_gds.addWidget(self.gds_path, 1)
        row_gds.addWidget(btn_pick_gds)
        non_pw_layout.addRow("Custom GDS file:", row_gds)

        # Row: custom landmarker points (µm)
        self.chk_custom_after = QtWidgets.QCheckBox("Custom landmarker points (µm)")
        self.chk_custom_after.toggled.connect(self._update_after_enabled)
        non_pw_layout.addRow(self.chk_custom_after)

        # Grid of spin boxes for TL, TR, BL, BR (x,y) in µm
        grid_after = QtWidgets.QGridLayout()
        def mkspin(default):
            sb = QtWidgets.QDoubleSpinBox()
            sb.setRange(-100000.0, 100000.0)
            sb.setDecimals(3)
            sb.setSingleStep(1.0)
            sb.setValue(float(default))
            sb.setMaximumWidth(120)
            return sb

        # Defaults from DEFAULT_AFTER_POINTS
        self.tl_x = mkspin(-50); self.tl_y = mkspin(60)
        self.tr_x = mkspin(70);  self.tr_y = mkspin(60)
        self.bl_x = mkspin(-50); self.bl_y = mkspin(-60)
        self.br_x = mkspin(70);  self.br_y = mkspin(-60)

        lab_bold = lambda s: (lambda L: (L.setStyleSheet("font-weight:600;"), L)[1])(QtWidgets.QLabel(s))
        grid_after.addWidget(lab_bold("TL x"), 0, 0); grid_after.addWidget(self.tl_x, 0, 1)
        grid_after.addWidget(lab_bold("TL y"), 0, 2); grid_after.addWidget(self.tl_y, 0, 3)
        grid_after.addWidget(lab_bold("TR x"), 1, 0); grid_after.addWidget(self.tr_x, 1, 1)
        grid_after.addWidget(lab_bold("TR y"), 1, 2); grid_after.addWidget(self.tr_y, 1, 3)
        grid_after.addWidget(lab_bold("BL x"), 2, 0); grid_after.addWidget(self.bl_x, 2, 1)
        grid_after.addWidget(lab_bold("BL y"), 2, 2); grid_after.addWidget(self.bl_y, 2, 3)
        grid_after.addWidget(lab_bold("BR x"), 3, 0); grid_after.addWidget(self.br_x, 3, 1)
        grid_after.addWidget(lab_bold("BR y"), 3, 2); grid_after.addWidget(self.br_y, 3, 3)

        self.after_points_panel = QtWidgets.QWidget()
        self.after_points_panel.setLayout(grid_after)
        non_pw_layout.addRow(self.after_points_panel)

        self._update_after_enabled(False)

        # Add to main grid below Run group
        grid.addWidget(self.btn_non_pw, 3, 0, 1, 2)
        grid.addWidget(self.non_pw_frame, 4, 0, 1, 2)

        self.status = self.statusBar()

    # --- helpers (Non-PW panel) ---
    def _toggle_non_pw_panel(self, checked: bool):
        self.non_pw_frame.setVisible(checked)
        self.btn_non_pw.setText("Non-Pengjie Wang Group Users ▲" if checked else "Non-Pengjie Wang Group Users ▼")

    def _update_after_enabled(self, checked: bool):
        self.after_points_panel.setEnabled(bool(checked))

    def _collect_after_points_str(self) -> str:
        if not self.btn_non_pw.isChecked() or not self.chk_custom_after.isChecked():
            return DEFAULT_AFTER_POINTS
        tl = (self.tl_x.value(), self.tl_y.value())
        tr = (self.tr_x.value(), self.tr_y.value())
        bl = (self.bl_x.value(), self.bl_y.value())
        br = (self.br_x.value(), self.br_y.value())
        def fmt(p): return f"({p[0]:.3f},{p[1]:.3f})"
        return ",".join([fmt(tl), fmt(tr), fmt(bl), fmt(br)])

    # --- standard helpers ---
    def add_images(self):
        filt = "Images (*.jpg *.jpeg *.png *.bmp *.tif *.tiff);;All files (*.*)"
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select images", "", filt)
        for p in paths:
            if not any(self.list.item(i).text() == p for i in range(self.list.count())):
                self.list.addItem(p)

    def clear_list(self, *_): self.list.clear()

    def choose_out_base(self):
        p = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose output base")
        if p: self.out_base.setText(p)

    def current_images(self): return [self.list.item(i).text() for i in range(self.list.count())]

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

    # NEW: default GDS resolver for PW Group users
    def resolve_gds(self) -> str:
        p0 = resource_path(GDS_BASENAME)
        if p0.exists(): return str(p0)
        return str(ABSOLUTE_GDS_FALLBACK)

    def build_argv(self):
        files = self.current_images()
        if not files: raise RuntimeError("No images selected.")
        out_base = self.out_base.text().strip()
        if not out_base: raise RuntimeError("Please choose an output base folder.")
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

        # ALWAYS set a GDS for the run:
        # - If Non-PW panel is open AND user picked one → use that.
        # - Else → use the canonical PW Group GDS.
        gds_override = None
        if self.btn_non_pw.isChecked():
            gds_override = self.gds_path.text().strip() or None
        argv.extend(["--gds-file", gds_override or self.resolve_gds()])

        return argv

    def run_clicked(self):
        try:
            argv = self.build_argv()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Invalid settings", str(e)); return

        self.progress.setVisible(True)
        self.log.append("Launching (external Python subprocess)…\n")
        worker = ExternalRunner(argv)
        worker.started_with_cmd.connect(lambda s: self.log.append(s))
        worker.line_ready.connect(self.log.insertPlainText)
        worker.logfile_ready.connect(lambda p: self.log.append(f"[Log file] {p}\n"))
        worker.finished_with_code.connect(self._run_finished)
        self._worker = worker
        worker.start()

    def _run_finished(self, code: int):
        self.progress.setVisible(False)
        self.log.append(f"\n[Process exited with code {code}]\n")

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWin(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
