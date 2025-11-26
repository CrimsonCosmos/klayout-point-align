"""
utils.py - Shared utility functions for PointAlign
"""
import sys
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=8)
def resource_path(rel_path: str) -> Path:
    """
    Return absolute path to bundled resource (PyInstaller-safe).

    In frozen mode (PyInstaller), resources are extracted to sys._MEIPASS.
    In development mode, resources are relative to the project root directory.

    Args:
        rel_path: Relative path to resource from project root

    Returns:
        Absolute path to the resource

    Examples:
        >>> resource_path("Test.GDS")
        Path("C:/Users/user/AppData/Local/Temp/_MEI123/Test.GDS")  # frozen
        Path("C:/path/to/project/Test.GDS")  # development
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use temporary extraction directory
        base = Path(sys._MEIPASS)
    else:
        # Running as script - find project root
        # This works from any file in the project by finding the directory
        # containing align_gui_aqua_qt.py (the main entry point)
        current_file = Path(__file__).resolve()

        # If utils.py is in project root, parent is project root
        # If it's in a subdirectory, we need to go up
        if (current_file.parent / "align_gui_aqua_qt.py").exists():
            base = current_file.parent
        else:
            # Search upward for project root
            base = current_file.parent
            while base.parent != base:  # Stop at filesystem root
                if (base / "align_gui_aqua_qt.py").exists():
                    break
                base = base.parent

    return base / rel_path


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """
    Get the project root directory.

    In frozen mode, returns sys._MEIPASS.
    In development mode, returns the directory containing align_gui_aqua_qt.py.

    Returns:
        Path to project root directory
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        current_file = Path(__file__).resolve()
        if (current_file.parent / "align_gui_aqua_qt.py").exists():
            return current_file.parent
        else:
            base = current_file.parent
            while base.parent != base:
                if (base / "align_gui_aqua_qt.py").exists():
                    return base
                base = base.parent
            # Fallback to current directory
            return Path(__file__).resolve().parent
