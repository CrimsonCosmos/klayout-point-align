# Test Suite

Comprehensive test suite for PointAlign application, covering unit tests, integration tests, and post-build verification.

## Test Categories

### 1. Unit Tests (Run During Development)

**`test_imports.py`** - Verify all critical imports work
- Catches PyInstaller packaging issues early
- Tests NumPy, OpenCV, PySide6, and custom modules
- Run: `python tests/test_imports.py`

**`test_alignment.py`** - Test alignment calculation algorithms
- Identity transformations
- Translation, scaling, rotation
- Homography vs affine transformations
- RMS error calculations
- Run: `python tests/test_alignment.py`

**`test_lys_io.py`** - Test .lys file reading/writing
- XML parsing and generation
- KLayout session file format
- GDS file existence
- Run: `python tests/test_lys_io.py`

### 2. Integration Tests (Run Before Building)

**`test_integration.py`** - Test component interactions
- GUI → subprocess command generation
- Resource path resolution (PyInstaller bundling)
- End-to-end workflow validation
- Error handling verification
- Run: `python tests/test_integration.py`

**`test_frozen_behavior.py`** - Test PyInstaller-specific behavior
- Console runner existence and configuration
- UTF-8 encoding support
- Frozen vs source execution detection
- Bundled script verification
- Run: `python tests/test_frozen_behavior.py`

### 3. Post-Build Tests (Run After PyInstaller Build)

**`test_post_build.py`** - Verify frozen application
- Both executables built correctly
- Required files bundled in `_internal/`
- Console runner actually runs
- Unicode support in console output
- PE header verification (GUI vs console subsystem)
- Run: `python tests/test_post_build.py dist/PointAlign_v1.1`

## Running All Tests

### Quick Test (Development)
```bash
# Run all unit tests
python tests/test_imports.py
python tests/test_alignment.py
python tests/test_lys_io.py
```

### Pre-Build Tests
```bash
# Run integration tests before building
python tests/test_integration.py
python tests/test_frozen_behavior.py
```

### Post-Build Verification
```bash
# After building with PyInstaller
python tests/test_post_build.py dist/PointAlign_v1.1
```

### Complete Test Suite (with pytest)
```bash
# Install pytest if needed
pip install pytest

# Run all tests
pytest tests/

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=. --cov-report=html
```

## Test-Driven Bug Prevention

These tests specifically catch bugs that have occurred in production:

### Bug: Run button opens new GUI window (Fixed 2025-11-03)
**Would be caught by:**
- `test_frozen_behavior.py::test_runner_uses_console_runner_not_main_exe`
- `test_integration.py::test_external_runner_command_construction`
- `test_post_build.py::test_console_runner_executable`

**How it helps:**
- Verifies `sys.executable` is not used as Python interpreter when frozen
- Ensures `console_runner.exe` exists and is used correctly
- Tests subprocess command construction

### Bug: Unicode encoding errors (Fixed 2025-11-03)
**Would be caught by:**
- `test_frozen_behavior.py::test_unicode_characters_in_output`
- `test_frozen_behavior.py::test_console_runner_forces_utf8`
- `test_post_build.py::test_unicode_support_in_console_runner`

**How it helps:**
- Verifies UTF-8 encoding configuration
- Tests actual Unicode character output
- Ensures `→ ✓ ⚠ ✗` characters work on Windows

## Adding New Tests

When you encounter a bug:

1. **Write a test that reproduces it** BEFORE fixing
2. **Verify the test fails** (red)
3. **Fix the bug**
4. **Verify the test passes** (green)
5. **Keep the test** to prevent regression

### Example:
```python
def test_new_feature():
    """
    Test that <feature> works correctly.

    This prevents regression of bug found on YYYY-MM-DD where...
    """
    # Test code here
    pass
```

## CI/CD Integration

Add to your build pipeline:

```yaml
# .github/workflows/build.yml (example)
- name: Run unit tests
  run: pytest tests/test_imports.py tests/test_alignment.py tests/test_lys_io.py

- name: Run integration tests
  run: pytest tests/test_integration.py tests/test_frozen_behavior.py

- name: Build with PyInstaller
  run: python -m PyInstaller PointAlign_folder.spec --noconfirm

- name: Run post-build tests
  run: python tests/test_post_build.py dist/PointAlign_v1.1
```

## Test Coverage Goals

- **Unit tests**: >80% coverage of core logic
- **Integration tests**: All user workflows covered
- **Post-build tests**: All PyInstaller-specific issues caught

## Troubleshooting

**Tests fail with import errors:**
- Ensure you're running from project root: `python tests/test_*.py`
- Check that `sys.path` modifications work for your setup

**Post-build tests can't find executables:**
- Build first: `python -m PyInstaller PointAlign_folder.spec --noconfirm`
- Use correct path: `python tests/test_post_build.py dist/PointAlign_v1.1`

**GUI tests fail without display:**
- Some integration tests require QApplication
- On headless systems, use `xvfb-run pytest` (Linux) or skip GUI tests

## Test Fixtures

Add test images and data to `tests/fixtures/`:
- `test_image.jpg` - Sample SEM/optical image with visible markers
- `test_markers.json` - Known marker positions for validation
- `test_output.lys` - Expected output format

(Currently these are optional - tests skip if not present)
