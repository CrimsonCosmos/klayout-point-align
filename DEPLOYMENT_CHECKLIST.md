# Point Align - Deployment Checklist

## Pre-Build Checklist

### ✅ Code Portability (COMPLETED)
- [x] Remove hard-coded user paths (`C:\Users\gehl2\...`)
- [x] Ensure `resource_path()` function works with PyInstaller's `_MEIPASS`
- [x] Template files (`Test_with_img.lys`, `Test.GDS`) included in `.spec` file

### 📦 Required Files to Ship

The following files MUST be bundled with the executable:

1. **Template Files** (defined in `PointAlign.spec`):
   - `Test_with_img.lys` - Default template session
   - `Test.GDS` - Default GDS layout file
   - `point_align_batch_runner_gui.py`
   - `klayout_point_align.py`

2. **Icon**:
   - `icon.ico` - Application icon

3. **Python Modules** (auto-included by PyInstaller):
   - PySide6
   - numpy
   - opencv-python
   - All files in `klayout_point_align/` folder
   - All files in `gui/` folder

### 🔧 Build Process

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Build Executable**:
   ```bash
   pyinstaller PointAlign.spec
   ```

3. **Output Location**:
   - Executable: `dist/PointAlign.exe`

4. **Test the Build**:
   - Run `dist/PointAlign.exe` on YOUR machine first
   - Verify template files load correctly
   - Test alignment with sample images
   - Test .lys file editor

---

## Deployment Testing Checklist

### 🖥️ Test on Clean Windows Machine

**CRITICAL**: Test on a computer that does NOT have Python installed!

- [ ] Copy `PointAlign.exe` to test machine
- [ ] Copy template files (`Test_with_img.lys`, `Test.GDS`) to same folder as exe
- [ ] Run the executable
- [ ] Verify no errors about missing DLLs or Python
- [ ] Test alignment workflow end-to-end
- [ ] Test LYS Editor tab
- [ ] Verify output .lys files open in KLayout

### 🔐 Permissions Test

- [ ] Run without administrator rights
- [ ] Verify it can write to Desktop
- [ ] Verify it can create `lys_sessions/` folder
- [ ] Verify preferences save correctly

### 🪟 Platform Testing

- [ ] Windows 10 (64-bit)
- [ ] Windows 11 (64-bit)

---

## Common Issues & Solutions

### Issue: "MSVCP140.dll missing" or "VCRUNTIME140.dll missing"
**Solution**: Install Microsoft Visual C++ Redistributable
- Download: https://aka.ms/vs/17/release/vc_redist.x64.exe

### Issue: Executable won't start (no error message)
**Solution**:
1. Run from command prompt to see errors: `PointAlign.exe`
2. Check Windows Event Viewer for application errors

### Issue: Template files not found
**Solution**:
1. Ensure `Test_with_img.lys` and `Test.GDS` are in same folder as .exe
2. Check `PointAlign.spec` includes these in `datas`

### Issue: Images break when .lys is moved
**Solution**: This is expected behavior. Users should:
1. Keep images and .lys in same folder structure, OR
2. Use absolute paths (current behavior)

---

## Distribution Package Structure

Recommended folder structure for distribution:

```
PointAlign_v1.0/
├── PointAlign.exe
├── Test_with_img.lys
├── Test.GDS
├── README.txt
└── examples/
    └── (sample images for testing)
```

---

## Known Limitations

1. **Image paths in .lys files**: Images are referenced by file path. If images are moved/deleted, .lys file will not display them.

2. **KLayout compatibility**: Base64 embedded images cause KLayout to crash. Must use file paths.

3. **Python version**: Built with Python 3.13. Should work on any Windows 10/11 without Python installed.

---

## Before Each Release

- [ ] Update version number in code
- [ ] Test build on clean Windows 10 machine
- [ ] Test build on clean Windows 11 machine
- [ ] Create release notes
- [ ] Tag git commit with version number
- [ ] Archive build artifacts

---

## Security Notes

- Application does NOT require administrator rights
- Does NOT modify system files
- Only writes to user-selected folders and Desktop
- No network access required
- No auto-updates (manual distribution)

