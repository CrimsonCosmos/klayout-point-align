
# gui/runner.py
# QThread wrapper that launches point_align_batch_runner_gui.py in a subprocess and streams output.

from __future__ import annotations
import os, sys, datetime, subprocess
from pathlib import Path
from qt_compat import QtCore
from diagnostic_logger import get_logger
from functools import lru_cache

@lru_cache(maxsize=8)
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

    def _run_inprocess(self, script_path: Path, log_path: Path, logger):
        """Run the batch script in-process (for single-file frozen builds)."""
        import runpy
        import io
        import contextlib

        # Redirect stdout/stderr to capture output
        output_buffer = io.StringIO()

        # Backup original sys.argv and replace with our arguments
        original_argv = sys.argv
        sys.argv = [str(script_path)] + self.argv_list

        pretty_cmd = f"python {script_path} " + " ".join(self.argv_list)
        self.started_with_cmd.emit(pretty_cmd + "\n")
        logger.log_process_start(sys.argv)

        try:
            with open(log_path, "w", encoding="utf-8", errors="replace") as lf:
                # Capture stdout and stderr
                with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
                    # Run the script as __main__
                    runpy.run_path(str(script_path), run_name="__main__")

                # Get all output
                output = output_buffer.getvalue()

                # Write to log and emit line by line
                for line in output.splitlines(keepends=True):
                    lf.write(line)
                    self.line_ready.emit(line)
                    logger.log_process_output(line.rstrip())

            logger.info("In-process execution completed successfully")
            self.finished_with_code.emit(0)

        except SystemExit as e:
            # Script called sys.exit()
            exit_code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
            logger.info(f"Script exited with code: {exit_code}")
            self.finished_with_code.emit(exit_code)

        except Exception as e:
            error_msg = f"[ERROR] In-process execution failed: {e}\n"
            logger.log_exception(e, "in-process execution")
            self.line_ready.emit(error_msg)
            self.finished_with_code.emit(1)

        finally:
            # Restore original sys.argv
            sys.argv = original_argv

    def run(self):
        logger = get_logger()

        # Use bundled runner script
        script_path = resource_path(self.script_rel)
        if not script_path.exists():
            error_msg = "[ERROR] Bundled runner script not found. Rebuild with --add-data \"point_align_batch_runner_gui.py;.\".\n"
            logger.error(f"Runner script not found: {script_path}")
            self.line_ready.emit(error_msg)
            self.finished_with_code.emit(1)
            return

        # Prepare log file
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(os.getenv("TEMP", str(Path.home()))) / f"PointAlign_run_{ts}.log"
        self.logfile_ready.emit(str(log_path))
        logger.info(f"Run log file: {log_path}")

        # Use bundled Python if frozen (PyInstaller), otherwise use system Python
        if getattr(sys, 'frozen', False):
            # Running from PyInstaller bundle - run in-process using runpy
            # We cannot use subprocess with console=False builds
            self._run_inprocess(script_path, log_path, logger)
            return
        else:
            # Running from source - prefer system Python
            cmd = None
            for cand in (["py", "-3"], ["py"], ["python3"], ["python"]):
                try:
                    subprocess.check_output(
                        cand + ["--version"], stderr=subprocess.STDOUT, text=True, timeout=3
                    )
                    cmd = cand + ["-u", str(script_path), *self.argv_list]
                    logger.debug(f"Using Python command: {cand}")
                    break
                except Exception:
                    continue
            if cmd is None:
                error_msg = "[ERROR] No system Python found on PATH.\n"
                logger.error("No Python interpreter found")
                self.line_ready.emit(error_msg)
                self.finished_with_code.emit(1)
                return

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        pretty_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        self.started_with_cmd.emit(pretty_cmd + "\n")
        logger.log_process_start(cmd)

        try:
            # CREATE_NO_WINDOW on Windows
            creationflags = 0x08000000 if os.name == "nt" else 0
            logger.debug(f"Starting subprocess with creationflags={creationflags}")
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
                    logger.log_process_output(line.rstrip())
                rc = proc.wait()
                logger.info(f"Process completed with exit code: {rc}")
        except Exception as e:
            error_msg = f"[ERROR] Failed to start external Python: {e}\n"
            logger.log_exception(e, "subprocess execution")
            self.line_ready.emit(error_msg)
            self.finished_with_code.emit(1)
            return

        self.finished_with_code.emit(rc)
