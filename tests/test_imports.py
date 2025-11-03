"""
Test that all critical imports work.
This catches most PyInstaller packaging issues.
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_numpy_import():
    """Test numpy imports correctly"""
    import numpy as np
    assert np.__version__ is not None
    # Test the problematic C extension
    from numpy._core import _multiarray_umath
    assert _multiarray_umath is not None


def test_opencv_import():
    """Test OpenCV imports correctly"""
    import cv2
    assert cv2.__version__ is not None


def test_pyside6_import():
    """Test PySide6 imports correctly"""
    from PySide6 import QtCore, QtGui, QtWidgets
    assert QtCore is not None
    assert QtGui is not None
    assert QtWidgets is not None


def test_klayout_point_align_import():
    """Test our main alignment module imports"""
    from klayout_point_align import run_point_alignment, parse_pts, reset_z_counter
    assert run_point_alignment is not None
    assert parse_pts is not None
    assert reset_z_counter is not None


def test_gui_modules_import():
    """Test GUI modules import"""
    from gui.align_tab import AlignTab
    from gui.runner import ExternalRunner
    assert AlignTab is not None
    assert ExternalRunner is not None


def test_lys_editor_import():
    """Test LYS editor imports"""
    from lys_editor_tab import LYSTab
    assert LYSTab is not None


if __name__ == "__main__":
    # Run tests manually
    test_numpy_import()
    print("✓ NumPy imports")

    test_opencv_import()
    print("✓ OpenCV imports")

    test_pyside6_import()
    print("✓ PySide6 imports")

    test_klayout_point_align_import()
    print("✓ klayout_point_align imports")

    test_gui_modules_import()
    print("✓ GUI modules import")

    test_lys_editor_import()
    print("✓ LYS editor imports")

    print("\nAll import tests passed!")
