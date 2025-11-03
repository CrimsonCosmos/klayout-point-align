# diagnostic_logger.py
# Comprehensive diagnostic and logging system for debugging user issues

import sys
import platform
import datetime
import traceback
from pathlib import Path
from typing import Optional
import logging

class DiagnosticLogger:
    """Enhanced logging system for debugging across different user environments."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path.cwd()
        self.log_file = self.log_dir / "PointAlign_debug.log"
        self.verbose = False

        # Set up file and console logging
        self.logger = logging.getLogger("PointAlign")
        self.logger.setLevel(logging.DEBUG)

        # File handler - always logs everything
        fh = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(fh)

        # Console handler - respects verbose mode
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(ch)

        self.console_handler = ch

    def set_verbose(self, enabled: bool):
        """Enable/disable verbose console output."""
        self.verbose = enabled
        self.console_handler.setLevel(logging.DEBUG if enabled else logging.INFO)

    def log_system_info(self):
        """Log comprehensive system information for debugging."""
        self.logger.info("="*80)
        self.logger.info(f"PointAlign Debug Log - Session started at {datetime.datetime.now()}")
        self.logger.info("="*80)

        # System information
        self.logger.info("SYSTEM INFORMATION:")
        self.logger.info(f"  OS: {platform.system()} {platform.release()} ({platform.version()})")
        self.logger.info(f"  Platform: {platform.platform()}")
        self.logger.info(f"  Architecture: {platform.machine()}")
        self.logger.info(f"  Processor: {platform.processor()}")
        self.logger.info(f"  Python Version: {sys.version}")
        self.logger.info(f"  Python Executable: {sys.executable}")

        # Check if running as frozen exe
        if getattr(sys, 'frozen', False):
            self.logger.info(f"  Running as: Frozen executable (PyInstaller)")
            self.logger.info(f"  Executable path: {sys.executable}")
            if hasattr(sys, '_MEIPASS'):
                self.logger.info(f"  Temp directory: {sys._MEIPASS}")
        else:
            self.logger.info(f"  Running as: Python script")
            self.logger.info(f"  Script directory: {Path(__file__).parent}")

        self.logger.info(f"  Working directory: {Path.cwd()}")

        # Python packages
        self.logger.info("\nINSTALLED PACKAGES:")
        try:
            import cv2
            self.logger.info(f"  OpenCV (cv2): {cv2.__version__}")
        except ImportError as e:
            self.logger.error(f"  OpenCV (cv2): NOT FOUND - {e}")
        except Exception as e:
            self.logger.error(f"  OpenCV (cv2): ERROR - {e}")

        try:
            from qt_compat import QT_BACKEND
            self.logger.info(f"  Qt Backend: {QT_BACKEND}")
            if QT_BACKEND == "PySide6":
                from PySide6 import __version__
                self.logger.info(f"  PySide6: {__version__}")
            elif QT_BACKEND == "PyQt6":
                from PyQt6.QtCore import QT_VERSION_STR
                self.logger.info(f"  PyQt6: {QT_VERSION_STR}")
        except Exception as e:
            self.logger.error(f"  Qt Backend: ERROR - {e}")

        try:
            import numpy as np
            self.logger.info(f"  NumPy: {np.__version__}")
        except ImportError as e:
            self.logger.error(f"  NumPy: NOT FOUND - {e}")
        except Exception as e:
            self.logger.error(f"  NumPy: ERROR - {e}")

        # Check for required files
        self.logger.info("\nREQUIRED FILES CHECK:")
        required_files = [
            "Test_with_img.lys",
            "Test.GDS",
            "icon.ico",
            "console_runner.py",
        ]

        for filename in required_files:
            filepath = Path(__file__).parent / filename
            if filepath.exists():
                self.logger.info(f"  ✓ {filename}: Found at {filepath}")
            else:
                self.logger.warning(f"  ✗ {filename}: NOT FOUND (expected at {filepath})")

        self.logger.info("="*80)

    def log_exception(self, exc: Exception, context: str = ""):
        """Log an exception with full stack trace."""
        if context:
            self.logger.error(f"EXCEPTION in {context}:")
        else:
            self.logger.error("EXCEPTION:")

        self.logger.error(f"  Type: {type(exc).__name__}")
        self.logger.error(f"  Message: {str(exc)}")
        self.logger.error("  Stack trace:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                self.logger.error(f"    {line}")

    def log_file_operation(self, operation: str, filepath: str, success: bool, details: str = ""):
        """Log file operations for debugging path issues."""
        status = "SUCCESS" if success else "FAILED"
        msg = f"File {operation}: {status} - {filepath}"
        if details:
            msg += f" ({details})"

        if success:
            self.logger.debug(msg)
        else:
            self.logger.error(msg)

    def log_process_start(self, command: list):
        """Log subprocess execution."""
        self.logger.info(f"Starting subprocess:")
        self.logger.info(f"  Command: {' '.join(command)}")

    def log_process_output(self, output: str, is_error: bool = False):
        """Log subprocess output."""
        for line in output.split('\n'):
            if line.strip():
                if is_error:
                    self.logger.error(f"  [STDERR] {line}")
                else:
                    self.logger.debug(f"  [STDOUT] {line}")

    def info(self, msg: str):
        """Log info message."""
        self.logger.info(msg)

    def debug(self, msg: str):
        """Log debug message."""
        self.logger.debug(msg)

    def warning(self, msg: str):
        """Log warning message."""
        self.logger.warning(msg)

    def error(self, msg: str):
        """Log error message."""
        self.logger.error(msg)

    def get_log_path(self) -> str:
        """Return the path to the log file."""
        return str(self.log_file.absolute())


# Global logger instance
_global_logger: Optional[DiagnosticLogger] = None


def get_logger() -> DiagnosticLogger:
    """Get or create the global diagnostic logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = DiagnosticLogger()
    return _global_logger


def init_logger(log_dir: Optional[Path] = None) -> DiagnosticLogger:
    """Initialize the global logger with optional custom directory."""
    global _global_logger
    _global_logger = DiagnosticLogger(log_dir)
    return _global_logger
