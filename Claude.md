# KlayoutAutoAlign - Project Documentation

## Project Overview

**PointAlign** is a GUI application developed at Wang Lab Group (University of Illinois Urbana-Champaign Materials Research Lab) in 2025. The program streamlines the process of aligning microscope images with .gds files in KLayout for 2D material research.

### Purpose
After a 2D material is created in the lab, it needs contacts deposited to measure condensed matter properties. This requires:
1. A 2D Computer Aided Design in KLayout (.gds file)
2. Proper alignment of the 2D material image with the .gds design file

PointAlign makes this alignment process faster and adds features specific to research workflows.

## Project Structure

### Main Entry Points
- `align_gui_aqua_qt.py` - Main GUI application (v1.1)
  - Composed of tabs using PySide6/Qt
  - Dark theme interface
  - Two main tabs: Align Tab and LYS Editor Tab

- `point_align_batch_runner_gui.py` - Batch processing helper
  - GUI file picker for selecting multiple images
  - Automatic fiducial detection with fallback to manual mode
  - Command-line arguments for automation

### Core Modules
- `klayout_point_align/` - Core alignment algorithm
  - `run_point_alignment()` - Main alignment function
  - `parse_pts()` - Point parsing utilities
  - `reset_z_counter()` - Z-index management

- `gui/` - GUI components
  - `align_tab.py` - Alignment interface tab
  - `runner.py` - External process runner

- `lys_editor_tab.py` - LYS file editor interface

- `qt_compat.py` - Qt compatibility layer for PySide6

### Template Files
- `Test_with_img.lys` - Default template session
- `Test.GDS` - Default GDS layout file
- `icon.ico` - Application icon

### Configuration Files
- `align_gui_prefs.json` - GUI preferences
- `align_tab_prefs.json` - Align tab preferences
- `gui_prefs.json` - General GUI preferences

## Dependencies

### Runtime Dependencies
- `numpy==2.2.6` - Numerical operations
- `opencv-python==4.12.0.88` - Image processing
- `PySide6==6.9.3` - Qt GUI framework

### Build Dependencies
- `pyinstaller==6.16.0` - Executable builder

## Build Process

### Prerequisites
- Python 3.13 (currently using Python 3.13.7)
- Windows 10/11 (64-bit)

### Building the Executable

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Build with PyInstaller**:
   ```bash
   pyinstaller PointAlign.spec
   ```

3. **Output**:
   - Executable: `dist/PointAlign.exe`
   - All dependencies bundled into single executable

### PyInstaller Configuration (PointAlign.spec)

The `.spec` file must include:
- Entry point: `align_gui_aqua_qt.py`
- Data files (templates): `Test_with_img.lys`, `Test.GDS`
- Icon: `icon.ico`
- Version info: `version.txt`
- Hidden imports: All modules in `klayout_point_align/` and `gui/`
- Console mode: Disabled (GUI app)

## Deployment

### Distribution Package Structure
```
PointAlign_v1.0/
├── PointAlign.exe
├── Test_with_img.lys
├── Test.GDS
├── README.txt
└── examples/
    └── (sample images for testing)
```

### Testing Requirements
- Test on clean Windows machine WITHOUT Python installed
- Verify template files load correctly
- Test alignment workflow end-to-end
- Test LYS Editor tab functionality
- Verify output .lys files open in KLayout

### Common Dependencies
Users may need to install:
- Microsoft Visual C++ Redistributable (for missing DLL errors)
- Download: https://aka.ms/vs/17/release/vc_redist.x64.exe

## Known Limitations

1. **Image Paths**: Images in .lys files are referenced by file path. Moving/deleting images will break the .lys file display.

2. **KLayout Compatibility**: Base64 embedded images cause KLayout to crash, so file paths must be used.

3. **Portability**: Avoid hard-coded user paths in code.

## Version Information

- Current Version: 1.1 (GUI), 1.0.0 (executable)
- Python Version: 3.13
- Platform: Windows 10/11 (64-bit)

## Development Notes

### Code Portability
- Use `resource_path()` function for PyInstaller compatibility with `_MEIPASS`
- No hard-coded paths like `C:\Users\gehl2\...`
- Template files must be included in `.spec` file

### Security
- No administrator rights required
- No system file modifications
- Only writes to user-selected folders and Desktop
- No network access required
- No auto-updates (manual distribution)

## Links

- Releases: https://github.com/wanglabq/KlayoutAutoAlign/releases
- Wiki/To-Dos: https://github.com/wanglabq/KlayoutAutoAlign/wiki
- Contact: Pengjie Wang <pengjiew@illinois.edu>

## Files to Review

- `DEPLOYMENT_CHECKLIST.md` - Complete deployment guide
- `USER_MANUAL.md` / `USER_MANUAL.html` - End-user documentation
- `README.md` - Project overview
