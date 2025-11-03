
# gui/runner.py
# QThread wrapper that launches point_align_batch_runner_gui.py in a subprocess and streams output.

from __future__ import annotations
import os, sys, datetime, subprocess
from pathlib import Path
from qt_compat import QtCore

def resource_path(rel_path: str) -> Path:
    """Return absolute path to bundled resource (PyInstaller-safe)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel_path

class ExternalRunner(QtCore.QThread):
    line_ready = QtCore.Signal(str)
    finished_with_code = QtCore.Signal(int)
    started_with_cmd = QtCore.Signal(str)
    logfile_ready = QtCore.Signal(str)

    def __init__(self, argv_list, parent=None, script_rel: str = "point_align_batch_runner_gui.py"):
        super().__init__(parent)
        self.argv_list = argv_list
        self.script_rel = script_rel

    def run(self):
        # Use bundled runner script
        script_path = resource_path(self.script_rel)
        if not script_path.exists():
            self.line_ready.emit(
                "[ERROR] Bundled runner script not found. Rebuild with --add-data \"point_align_batch_runner_gui.py;.\".\n"
            )
            self.finished_with_code.emit(1)
            return

        # Prepare log file
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(os.getenv("TEMP", str(Path.home()))) / f"PointAlign_run_{ts}.log"
        self.logfile_ready.emit(str(log_path))

        # Use bundled Python if frozen (PyInstaller), otherwise use system Python
        if getattr(sys, 'frozen', False):
            # Running from PyInstaller bundle - use console_runner.exe
            # sys.executable would point to the GUI app, not a Python interpreter
            console_runner = Path(sys.executable).parent / "console_runner.exe"
            if not console_runner.exists():
                self.line_ready.emit(
                    f"[ERROR] Console runner not found at {console_runner}. Rebuild with updated spec.\n"
                )
                self.finished_with_code.emit(1)
                return
            cmd = [str(console_runner), str(script_path), *self.argv_list]
        else:
            # Running from source - prefer system Python
            cmd = None
            for cand in (["py", "-3"], ["py"], ["python3"], ["python"]):
                try:
                    subprocess.check_output(
                        cand + ["--version"], stderr=subprocess.STDOUT, text=True, timeout=3
                    )
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
            # CREATE_NO_WINDOW on Windows
            creationflags = 0x08000000 if os.name == "nt" else 0
            with open(log_path, "w", encoding="utf-8", errors="replace") as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    creationflags=creationflags,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    lf.write(line)
                    lf.flush()
                    self.line_ready.emit(line)
                rc = proc.wait()
        except Exception as e:
            self.line_ready.emit(f"[ERROR] Failed to start external Python: {e}\n")
            self.finished_with_code.emit(1)
            return

        self.finished_with_code.emit(rc)
