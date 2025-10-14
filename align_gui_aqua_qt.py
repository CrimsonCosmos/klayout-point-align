# align_gui_aqua_qt.py — Aqua-styled GUI (PySide6/Qt)
# FIX: Always run the worker in an external Python subprocess to avoid Qt-in-Qt freezes.
#
# Build hint (bundle runner + lys):
# pyinstaller --onefile --noconsole --name PointAlign --icon icon.ico ^
#   --hidden-import point_align_batch_runner_gui --hidden-import klayout_point_align ^
#   --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 ^
#   --add-data "Test_with_img.lys;." --add-data "point_align_batch_runner_gui.py;." ^
#   align_gui_aqua_qt.py

import os, sys, datetime, subprocess
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets

APP_TITLE = "Point Align"
COMBINED_FILENAME = "session_combined.lys"
PREFS_NAME = "align_gui_prefs.json"

LYS_BASENAME = "Test_with_img.lys"
ABSOLUTE_LYS_FALLBACK = Path(r"C:\Users\gehl2\Test_with_img.lys")
AFTER_POINTS = "(-50,60),(70,60),(-50,-60),(70,-60)"
ALWAYS_AUTO_REVIEW = True  # opens picker pre-seeded after autodetect (in external process)

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
        self.resize(980, 700)

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

        self.status = self.statusBar()

    # --- helpers ---
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

    def build_argv(self):
        files = self.current_images()
        if not files: raise RuntimeError("No images selected.")
        out_base = self.out_base.text().strip()
        if not out_base: raise RuntimeError("Please choose an output base folder.")
        dated = self.compute_dated_folder(Path(out_base)); dated.mkdir(parents=True, exist_ok=True)
        argv = [
            "--files", *files,
            "--lys-in", self.resolve_lys(),
            "--after", AFTER_POINTS,
            "--affine",
            "--out-dir", str(dated),
            "--combined-out", str(dated / COMBINED_FILENAME),
        ]
        if ALWAYS_AUTO_REVIEW:
            argv.append("--auto-review")
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
