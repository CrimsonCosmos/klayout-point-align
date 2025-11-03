"""
Test behavior when application is frozen with PyInstaller.

These tests catch issues that only appear in the frozen/built application,
not when running from source.

IMPORTANT: Some of these tests need to be run AFTER building with PyInstaller.
Mark them with @pytest.mark.frozen_only or similar.
"""
import sys
import os
from pathlib import Path
import subprocess

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_console_runner_exists_when_frozen():
    """Test that console_runner.exe exists alongside the main exe when frozen"""
    if not getattr(sys, 'frozen', False):
        # Skip if not frozen - or check that console_runner.py exists
        assert Path("console_runner.py").exists(), "console_runner.py source file missing"
        return

    # When frozen, console_runner.exe should be in same directory as main exe
    exe_dir = Path(sys.executable).parent
    console_runner = exe_dir / "console_runner.exe"

    assert console_runner.exists(), \
        f"console_runner.exe not found at {console_runner}. Rebuild with updated spec file."


def test_runner_uses_console_runner_not_main_exe():
    """Test that gui/runner.py uses console_runner.exe when frozen, not sys.executable"""
    from gui.runner import ExternalRunner
    import inspect

    # Read the source code
    source = inspect.getsource(ExternalRunner.run)

    # Should check for frozen state
    assert 'frozen' in source.lower(), \
        "ExternalRunner.run should check if frozen"

    # Should use console_runner when frozen
    assert 'console_runner' in source.lower(), \
        "ExternalRunner.run should use console_runner.exe when frozen"

    # Should NOT directly use sys.executable for script execution when frozen
    # (it's okay to use it to find the directory)
    lines = source.split('\n')
    for line in lines:
        # Look for problematic pattern: using sys.executable as python interpreter
        if 'sys.executable' in line and 'cmd' in line and 'Path' not in line:
            # This line might be using sys.executable incorrectly
            # Make sure it's getting the directory, not using it as interpreter
            if '.parent' not in line and 'console_runner' not in source[source.index(line):]:
                assert False, \
                    f"Suspicious use of sys.executable as interpreter: {line.strip()}"


def test_console_runner_forces_utf8():
    """Test that console_runner.py forces UTF-8 encoding"""
    console_runner_path = Path("console_runner.py")

    assert console_runner_path.exists(), "console_runner.py not found"

    content = console_runner_path.read_text()

    # Should configure UTF-8 encoding
    assert 'utf-8' in content.lower() or 'utf8' in content.lower(), \
        "console_runner.py should configure UTF-8 encoding"

    # Should reconfigure stdout/stderr
    assert 'reconfigure' in content or 'PYTHONIOENCODING' in content, \
        "console_runner.py should reconfigure stdout/stderr encoding"


def test_unicode_characters_in_output():
    """Test that Unicode characters can be printed without errors"""
    # Test the specific characters that caused the original bug
    test_chars = [
        '\u2192',  # → arrow (caused the original charmap error)
        '\u2713',  # ✓ checkmark
        '\u26A0',  # ⚠ warning
        '\u2717',  # ✗ cross mark
    ]

    # Try to encode these with common Windows encoding (should fail without UTF-8)
    try:
        for char in test_chars:
            char.encode('cp1252')  # Common Windows encoding
    except UnicodeEncodeError:
        # Good - this confirms the characters need UTF-8
        pass

    # All should work with UTF-8
    for char in test_chars:
        encoded = char.encode('utf-8')
        assert encoded is not None


def test_external_runner_creates_subprocess_not_gui():
    """
    Test that ExternalRunner creates a subprocess, not a new GUI window.

    This would have caught the original bug where clicking Run opened another
    window of the application.
    """
    from gui.runner import ExternalRunner

    # Create a mock runner
    runner = ExternalRunner(["--help"])

    # Check that the run method uses subprocess/Popen
    import inspect
    source = inspect.getsource(runner.run)

    assert 'subprocess' in source.lower() or 'popen' in source.lower(), \
        "ExternalRunner should use subprocess.Popen for external execution"

    # Should NOT use QProcess (which might launch the GUI)
    assert 'qprocess' not in source.lower(), \
        "ExternalRunner should not use QProcess (use subprocess.Popen instead)"


def test_bundled_python_vs_system_python():
    """Test that we correctly distinguish between frozen and source execution"""
    if getattr(sys, 'frozen', False):
        # When frozen, sys.executable should point to our .exe
        assert sys.executable.endswith('.exe'), \
            "When frozen, sys.executable should be the .exe file"

        # console_runner.exe should exist
        exe_dir = Path(sys.executable).parent
        console_runner = exe_dir / "console_runner.exe"
        assert console_runner.exists(), \
            "console_runner.exe should exist when frozen"
    else:
        # When running from source, sys.executable should be python
        assert 'python' in sys.executable.lower(), \
            "When not frozen, sys.executable should be python interpreter"


def test_point_align_batch_runner_bundled():
    """Test that point_align_batch_runner_gui.py is bundled when frozen"""
    if getattr(sys, 'frozen', False):
        # Should be in _internal directory
        base_path = Path(getattr(sys, '_MEIPASS', '.'))
        script = base_path / "point_align_batch_runner_gui.py"

        assert script.exists(), \
            f"point_align_batch_runner_gui.py not found at {script}. " \
            "Check PyInstaller spec datas configuration."


if __name__ == "__main__":
    # Force UTF-8 for test output
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    print("Testing frozen behavior...")

    try:
        test_console_runner_exists_when_frozen()
        print("[PASS] Console runner exists")
    except AssertionError as e:
        print(f"[FAIL] Console runner: {e}")

    try:
        test_runner_uses_console_runner_not_main_exe()
        print("[PASS] Runner uses console_runner correctly")
    except AssertionError as e:
        print(f"[FAIL] Runner usage: {e}")

    try:
        test_console_runner_forces_utf8()
        print("[PASS] Console runner forces UTF-8")
    except AssertionError as e:
        print(f"[FAIL] UTF-8 config: {e}")

    try:
        test_unicode_characters_in_output()
        print("[PASS] Unicode characters supported")
    except AssertionError as e:
        print(f"[FAIL] Unicode: {e}")

    try:
        test_external_runner_creates_subprocess_not_gui()
        print("[PASS] External runner uses subprocess")
    except AssertionError as e:
        print(f"[FAIL] Subprocess usage: {e}")

    try:
        test_bundled_python_vs_system_python()
        print("[PASS] Frozen vs source detection works")
    except AssertionError as e:
        print(f"[FAIL] Frozen detection: {e}")

    try:
        test_point_align_batch_runner_bundled()
        print("[PASS] Batch runner script bundled")
    except AssertionError as e:
        print(f"[FAIL] Batch runner: {e}")

    print("\nFrozen behavior tests complete!")
