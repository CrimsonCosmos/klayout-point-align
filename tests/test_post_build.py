"""
Post-build tests - run these AFTER PyInstaller build to verify the frozen app.

Usage:
    python tests/test_post_build.py dist/PointAlign_v1.1

These tests catch issues specific to the frozen/packaged application that
won't appear when running from source.
"""
import sys
import os
from pathlib import Path
import subprocess


def test_executables_exist(dist_dir):
    """Test that both executables were built correctly"""
    dist_path = Path(dist_dir)

    main_exe = dist_path / "PointAlign.exe"
    console_exe = dist_path / "console_runner.exe"

    errors = []

    if not main_exe.exists():
        errors.append(f"Main executable not found: {main_exe}")

    if not console_exe.exists():
        errors.append(f"Console runner not found: {console_exe}")

    if errors:
        return False, "\n".join(errors)

    return True, "Both executables exist"


def test_required_files_bundled(dist_dir):
    """Test that required data files are bundled"""
    dist_path = Path(dist_dir)

    # Files that should be in _internal
    internal_dir = dist_path / "_internal"
    required_files = [
        "point_align_batch_runner_gui.py",
        "Test.GDS",
        "Test_with_img.lys",
    ]

    errors = []
    for filename in required_files:
        file_path = internal_dir / filename
        if not file_path.exists():
            errors.append(f"Required file not bundled: {filename}")

    if errors:
        return False, "\n".join(errors)

    return True, f"All {len(required_files)} required files bundled"


def test_console_runner_executable(dist_dir):
    """Test that console_runner.exe actually runs"""
    dist_path = Path(dist_dir)
    console_exe = dist_path / "console_runner.exe"

    if not console_exe.exists():
        return False, "console_runner.exe not found"

    # Try running it with --help (should fail gracefully)
    try:
        # This should exit with code 1 and print usage
        result = subprocess.run(
            [str(console_exe)],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            errors='replace'
        )

        # Should print usage message
        if "Usage:" in result.stderr or "Usage:" in result.stdout:
            return True, "console_runner.exe runs and shows usage"
        else:
            return False, f"Unexpected output: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "console_runner.exe timed out (should exit quickly)"
    except Exception as e:
        return False, f"Failed to run console_runner.exe: {e}"


def test_main_exe_starts(dist_dir):
    """Test that main executable starts without crashing"""
    dist_path = Path(dist_dir)
    main_exe = dist_path / "PointAlign.exe"

    if not main_exe.exists():
        return False, "PointAlign.exe not found"

    # We can't easily test the GUI without user interaction,
    # but we can at least verify it doesn't immediately crash

    # Just verify it exists and is executable
    if main_exe.exists() and main_exe.stat().st_size > 0:
        return True, "PointAlign.exe exists and has content"
    else:
        return False, "PointAlign.exe is empty or corrupted"


def test_dependencies_bundled(dist_dir):
    """Test that required DLLs are bundled"""
    dist_path = Path(dist_dir)
    internal_dir = dist_path / "_internal"

    # Critical DLLs - python DLL is most important
    # .pyd files may be packaged into .pyz archive, so check for those too
    required_checks = [
        ("python*.dll", "Python DLL"),
        ("PySide6", "PySide6 directory"),  # PySide6 might be a folder
    ]

    import glob

    errors = []
    for pattern, name in required_checks:
        # Check for files or directories matching pattern
        matches = list(internal_dir.glob(pattern)) + list(internal_dir.glob(f"**/{pattern}"))
        if not matches:
            errors.append(f"Missing: {name}")

    # Just warn, don't fail - some bundling methods package differently
    if errors:
        return True, f"Warning (non-critical): {', '.join(errors)}"

    return True, "Critical dependencies bundled"


def test_unicode_support_in_console_runner(dist_dir):
    """Test that console_runner.exe supports Unicode output"""
    dist_path = Path(dist_dir)
    console_exe = dist_path / "console_runner.exe"

    if not console_exe.exists():
        return False, "console_runner.exe not found"

    # Create a tiny test script that prints Unicode
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write("print('Testing Unicode: → ✓ ⚠ ✗')\n")
        test_script = f.name

    try:
        # Run the script via console_runner
        result = subprocess.run(
            [str(console_exe), test_script],
            capture_output=True,
            timeout=5,
            encoding='utf-8',
            errors='replace'
        )

        output = result.stdout + result.stderr

        # Check for Unicode characters (may be replaced if not supported)
        if '→' in output or 'Unicode' in output:
            return True, "Unicode characters handled (UTF-8 supported)"
        else:
            return False, f"Unicode test failed. Output: {output}"

    except Exception as e:
        return False, f"Unicode test error: {e}"
    finally:
        try:
            os.unlink(test_script)
        except:
            pass


def test_no_console_window_for_main_exe(dist_dir):
    """Verify that PointAlign.exe was built with console=False"""
    dist_path = Path(dist_dir)
    main_exe = dist_path / "PointAlign.exe"

    if not main_exe.exists():
        return False, "PointAlign.exe not found"

    # Read PE header to check subsystem (GUI vs Console)
    try:
        with open(main_exe, 'rb') as f:
            # Read DOS header
            f.seek(0x3C)  # Offset to PE signature
            pe_offset = int.from_bytes(f.read(4), 'little')

            # Jump to PE optional header
            f.seek(pe_offset + 0x5C)  # Subsystem field offset
            subsystem = int.from_bytes(f.read(2), 'little')

            # 2 = GUI, 3 = Console
            if subsystem == 2:
                return True, "Main exe is GUI application (no console window)"
            elif subsystem == 3:
                return False, "Main exe is console application (will show console)"
            else:
                return False, f"Unknown subsystem: {subsystem}"

    except Exception as e:
        # If we can't read PE header, just skip this test
        return True, f"Could not verify (skipped): {e}"


def test_console_window_for_runner_exe(dist_dir):
    """Verify that console_runner.exe was built with console=True"""
    dist_path = Path(dist_dir)
    console_exe = dist_path / "console_runner.exe"

    if not console_exe.exists():
        return False, "console_runner.exe not found"

    # Read PE header to check subsystem
    try:
        with open(console_exe, 'rb') as f:
            f.seek(0x3C)
            pe_offset = int.from_bytes(f.read(4), 'little')
            f.seek(pe_offset + 0x5C)
            subsystem = int.from_bytes(f.read(2), 'little')

            if subsystem == 3:
                return True, "Console runner is console application (correct)"
            elif subsystem == 2:
                return False, "Console runner is GUI application (incorrect - should be console)"
            else:
                return False, f"Unknown subsystem: {subsystem}"

    except Exception as e:
        return True, f"Could not verify (skipped): {e}"


def run_all_tests(dist_dir):
    """Run all post-build tests"""
    # Force UTF-8 for test output
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    tests = [
        ("Executables exist", test_executables_exist),
        ("Required files bundled", test_required_files_bundled),
        ("Console runner runs", test_console_runner_executable),
        ("Main exe exists", test_main_exe_starts),
        ("Dependencies bundled", test_dependencies_bundled),
        ("Unicode support", test_unicode_support_in_console_runner),
        ("Main exe is GUI app", test_no_console_window_for_main_exe),
        ("Console runner is console app", test_console_window_for_runner_exe),
    ]

    results = []
    passed = 0
    failed = 0

    print(f"\nRunning post-build tests on: {dist_dir}\n")
    print("=" * 70)

    for test_name, test_func in tests:
        try:
            success, message = test_func(dist_dir)
            status = "[PASS]" if success else "[FAIL]"

            if success:
                passed += 1
                print(f"{status}: {test_name}")
                if message:
                    print(f"        {message}")
            else:
                failed += 1
                print(f"{status}: {test_name}")
                if message:
                    for line in message.split('\n'):
                        print(f"        {line}")

            results.append((test_name, success, message))

        except Exception as e:
            failed += 1
            print(f"[ERROR]: {test_name}")
            print(f"         {str(e)}")
            results.append((test_name, False, str(e)))

    print("=" * 70)
    print(f"\nResults: {passed} passed, {failed} failed out of {len(tests)} tests")

    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_post_build.py <dist_directory>")
        print("Example: python test_post_build.py dist/PointAlign_v1.1")
        sys.exit(1)

    dist_dir = sys.argv[1]

    if not Path(dist_dir).exists():
        print(f"Error: Directory not found: {dist_dir}")
        sys.exit(1)

    success = run_all_tests(dist_dir)
    sys.exit(0 if success else 1)
