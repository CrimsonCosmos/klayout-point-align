# Point Align - User Manual
**Version 1.1**

---

## QUICK START - 5 Steps to Align Images

### Step 1: Add Your Images
- Click **"Add images..."** button
- Select your microscope images (JPG, PNG, TIF, etc.)

### Step 2: Set Output Location
- Click **"Browse Folder..."**
- Choose where to save your aligned .lys file

### Step 3: Click "Run Alignment"
- Click the green **"Run Alignment"** button
- Point Picker window opens

### Step 4: Click the 4 Alignment Points
**Click in this exact order on your image:**

```
Point Order:
1. Top-Left intersection
2. Top-Right intersection
3. Bottom-Left intersection
4. Bottom-Right intersection
```

**What to click:** The 4 intersections where the **innermost L-shapes meet the box corners**

![Alignment Points Diagram](example_points_for_manual.png)

The diagram shows the 4 alignment points (white crosshairs) where the L-shaped alignment marks meet the corner boxes. Click in order: Top-Left, Top-Right, Bottom-Left, Bottom-Right.

### Step 5: View in KLayout
- Double-click the output `.lys` file to open it in KLayout

---

For more details, see the full manual below.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Getting Started](#getting-started)
4. [Main Features](#main-features)
5. [Align Tab - Step-by-Step Guide](#align-tab-step-by-step-guide)
6. [LYS Editor Tab](#lys-editor-tab)
7. [Understanding Output Files](#understanding-output-files)
8. [Tips & Best Practices](#tips--best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Technical Details](#technical-details)

---

## Introduction

Point Align aligns microscope images to GDS (GDSII) layout files for viewing in KLayout. It uses point-based alignment to overlay images onto the design layout.

### What does Point Align do?

1. Takes your microscope images (JPG, PNG, TIF, etc.)
2. Lets you mark 4 corresponding points on the image and GDS layout
3. Calculates the transformation matrix to align them
4. Creates a KLayout session file (.lys) with perfectly aligned images
5. Allows you to edit and manage your .lys session files

### Use Cases

- **Failure Analysis**: Overlay SEM/optical images on chip layouts
- **Process Verification**: Compare fabricated devices to design
- **Documentation**: Create aligned image sets for reports
- **Quality Control**: Visual inspection of manufactured chips

---

## Installation

### Standalone Executable (Recommended)

No Python installation required.

1. Download `PointAlign.exe`
2. Double-click to launch

### System Requirements

- Windows 10 or Windows 11 (64-bit)
- 4GB RAM minimum (8GB recommended)
- 500MB free disk space
- Optional: KLayout installed to open .lys output files

### First Launch

When you first run Point Align:
- Windows may show a security warning (click "More info" → "Run anyway")
- The program creates configuration files in your user folder
- Default templates are loaded automatically

---

## Getting Started

### Quick Start Workflow

1. **Launch Point Align**
2. Click the **"Align"** tab (default view)
3. **Add images** you want to align
4. Choose **output location**
5. Configure **alignment points** (or use defaults)
6. Click **"Run Alignment"**
7. Open the resulting `.lys` file in KLayout

---

## Main Features

Point Align has two main tabs:

### 1. Align Tab
- Primary workflow for aligning images
- Point selection and coordinate entry
- Batch processing multiple images
- Output to KLayout session files

### 2. LYS Editor Tab
- Edit existing .lys session files
- Reorder images
- Delete images from sessions
- Manage multiple .lys files side-by-side
- Open .lys files directly in KLayout

---

## Align Tab - Step-by-Step Guide

### Step 1: Add Input Images

**Option A: Browse for Images**
1. Click **"Add images..."** button
2. Select one or more image files
3. Supported formats: JPG, PNG, TIF, BMP, etc.

**Option B: Drag & Drop**
- Drag image files directly into the list

**Managing Your Image List:**
- Thumbnails show preview of each image
- Hover over image name to see full path
- Click **"Clear list"** to remove all images

### Step 2: Choose Output Location

You have two output modes:

#### Mode A: Create New .lys in Folder
1. Select radio button: **"Create new .lys in folder"**
2. Click **"Browse Folder..."**
3. Choose where to save the output
4. Output file will be named: `Aligned-YYYY-MM-DD-N.lys`
   - Example: `Aligned-2025-11-02-1.lys`
   - Number increments automatically if file exists

#### Mode B: Add to Existing .lys File
1. Select radio button: **"Add to existing .lys file"**
2. Click **"Browse .lys..."**
3. Choose an existing .lys session file
4. New images will be appended to that session

### Step 3: Select Template .lys

The **template .lys** defines:
- Default KLayout view settings
- Layer visibility
- Display preferences

**Default Template:**
- `Test_with_img.lys` is bundled with the application
- Located in program folder

**Custom Template:**
1. Click **"Browse..."** next to .lys template field
2. Select your own .lys file
3. This .lys must already have proper KLayout settings

### Step 4: Select GDS Layout File

**What is the GDS file?**
- Contains the chip/circuit design layout
- Your images will be aligned to this layout

**How to specify:**
1. Click **"Browse..."** next to GDS field
2. Select your `.gds` or `.oasis` file

**Default GDS:**
- `Test.GDS` is bundled for testing

### Step 5: Configure Alignment Mode

Point Align supports two alignment modes:

#### PW Group Mode (Default - Recommended)
- **Best for**: Standardized alignment workflows
- **Alignment Points**: Pre-defined 4-point pattern
  - Top-Left: (-50, 60) µm
  - Top-Right: (70, 60) µm
  - Bottom-Left: (-50, -60) µm
  - Bottom-Right: (70, -60) µm
- **How it works**: You mark 4 points on your image, program knows the GDS coordinates

**To use PW Group mode:**
1. Select **"PW Group"** radio button
2. Click **"Run Alignment"**
3. Interactive picker window opens for each image

#### Non-PW Group Mode (Custom Points)
- **Best for**: Custom alignment workflows, non-standard layouts
- **Flexibility**: Define your own coordinate pairs

**To use Non-PW Group mode:**
1. Select **"Non-PW Group"** radio button
2. Check **"Custom alignment points"** if you want to change defaults
3. Enter GDS coordinates in µm for each of 4 points:
   - **Top-Left** (X, Y)
   - **Top-Right** (X, Y)
   - **Bottom-Left** (X, Y)
   - **Bottom-Right** (X, Y)

**Affine vs Perspective:**
- ☑ **Affine transform** (recommended): Preserves parallel lines, better for most microscope images
- ☐ **Perspective transform**: Use only if image has significant perspective distortion

### Step 6: Point Selection (Interactive)

After clicking **"Run Alignment"**, the Point Picker window opens:

#### Point Picker Window Controls

**Navigation:**
- **Mouse Wheel**: Zoom in/out
- **Left-click + Drag**: Pan the image
- **Right-click**: Reset zoom

**Selecting Points:**
1. **Zoom in** to the first alignment mark
2. **Left-click** precisely on the alignment point
3. A **red crosshair** appears where you clicked
4. Repeat for all 4 points (Top-Left → Top-Right → Bottom-Left → Bottom-Right)

**Order is critical! Always mark points in this order:**
1. **Top-Left** corner
2. **Top-Right** corner
3. **Bottom-Left** corner
4. **Bottom-Right** corner

**If you make a mistake:**
- Click **"Clear Points"** to reset all points
- Click **"Undo Last"** to remove the most recent point

**When done:**
- Click **"Accept"** to confirm points
- Click **"Skip Image"** to exclude this image

#### Alignment Quality (RMS Error)

After processing, each image shows alignment quality (RMS error):
- **RMS < 0.5 µm**: Excellent alignment
- **RMS 0.5-2 µm**: Good (acceptable for most use cases)
- **RMS > 2 µm**: Poor (check your points)

### Step 7: View Results

The aligned .lys file is created in your output folder.

To view in KLayout:
1. Locate output .lys file
2. Double-click to open in KLayout
3. Your images appear overlaid on the GDS layout

**Output Location:**
- For "new folder" mode: Check the output folder you selected
- For "existing .lys" mode: Images added to that .lys file

---

## LYS Editor Tab

The LYS Editor lets you manage and edit .lys session files.

### Opening a .lys File

**Left Editor:**
1. Click **"Browse..."** button
2. Select a .lys file
3. Images in that session appear in the list

**Second Editor (Optional):**
- Click **"Show Second Editor ▶"** for side-by-side editing
- Useful for copying images between sessions

### Viewing Images

**Image List:**
- Shows all images in the .lys session
- Thumbnails for quick identification
- File names displayed

**Preview an Image:**
- **Double-click** any image in the list
- Zoomable preview window opens
- Mouse wheel to zoom, drag to pan

### Reordering Images

Images stack in KLayout based on list order (z-position).

**Method 1: Drag & Drop**
- Click and hold an image
- Drag to new position
- Release to drop

**Method 2: Buttons**
- Select image(s)
- Click **"Up"** or **"Down"** buttons
- Keyboard shortcuts: Alt+Up / Alt+Down

### Deleting Images

1. Select one or more images
2. Click **"Delete"** button (or press Delete key)
3. Confirm deletion
4. **Remember to Save!**

### Managing GDS Files

**View GDS Files:**
- GDS files list shows all layouts in the session
- Usually just one GDS per session

**Add GDS:**
1. Click **"Add..."**
2. Select .gds or .oasis file
3. GDS added to session

**Remove GDS:**
1. Select GDS in list
2. Click **"Remove"**

**Open Folder:**
- Select GDS
- Click **"Open Folder"** to view location

### Copying Between Sessions

**With Two Editors Open:**

1. Click **"Show Second Editor"** button
2. Open source .lys in left editor
3. Open destination .lys in right editor
4. Select images in source list
5. Click **"→ COPY IMAGES →"**
6. Images copied to destination
7. **Save both sessions!**

### Saving Changes

**Save:**
- Click **"Save"** (Ctrl+S)
- Overwrites current .lys file
- Backup created automatically in `lys_sessions/backups/`

**Save As:**
- Click **"Save As..."** (Ctrl+Shift+S)
- Choose new filename/location
- Original file unchanged

**Open in KLayout:**
- Click **"Open in KLayout"** button
- Launches KLayout with current session
- Prompts to save if unsaved changes

---

## Understanding Output Files

### .lys Session Files

**What is a .lys file?**
- KLayout session file (XML format)
- Contains:
  - References to GDS layout files
  - References to aligned images
  - Transformation matrices for each image
  - KLayout view settings (zoom, layers, etc.)

**Image References:**
- .lys files store **file paths** to images
- Images are **NOT embedded** in .lys files
- **Important**: Keep images and .lys in same folder structure

**Structure:**
```
Desktop/
├── Aligned-2025-11-02.lys
├── image1.jpg  ← Referenced by .lys
├── image2.jpg  ← Referenced by .lys
└── Test.GDS    ← Referenced by .lys
```

### Backups

**Automatic Backups:**
- Every save creates backup
- Location: `lys_sessions/backups/`
- Naming: `<filename>.lys.bak`
- Keeps last version before each save

**Manual Backups:**
- Use "Save As..." with new name
- Archive important sessions regularly

---

## Tips & Best Practices

### Image Preparation

**Best Results:**
- Use high-resolution images (300+ DPI)
- Ensure alignment marks are clearly visible
- Avoid motion blur or out-of-focus images
- Consistent lighting helps

**Supported Formats:**
- JPEG (.jpg, .jpeg) - Common, compressed
- PNG (.png) - Lossless, recommended
- TIFF (.tif, .tiff) - High quality, large files
- BMP, GIF, WebP also supported

### Alignment Point Selection

**For Best Accuracy:**

1. **Zoom in as much as possible** before clicking
2. **Use sharp, well-defined features**:
   - Pad corners
   - Via centers
   - Alignment mark crosshairs
3. **Avoid fuzzy/blurry areas**
4. **Spread points widely** - don't cluster them
5. **Be consistent** across all images

Common mistakes to avoid:
- Clicking too quickly without zooming
- Using soft/rounded features
- Selecting points too close together
- Wrong point order

### Batch Processing

**Processing Multiple Images:**
1. Add all images at once
2. Point picker processes each sequentially
3. Review RMS errors after completion
4. Re-process any poor alignments

**Time-Saving Tips:**
- Pre-sort images by sample/region
- Use consistent naming (image1.jpg, image2.jpg, etc.)
- Keep alignment marks in same relative positions

### File Organization

**Recommended Folder Structure:**
```
Project_Name/
├── raw_images/
│   ├── sample1_image1.jpg
│   ├── sample1_image2.jpg
│   └── ...
├── aligned_sessions/
│   ├── Sample1_Aligned.lys
│   ├── Sample2_Aligned.lys
│   └── ...
└── layouts/
    └── chip_design.gds
```

### Working with KLayout

**Opening .lys Files:**
- Double-click .lys file (if KLayout is associated)
- Or: Open KLayout → File → Restore Session

**Adjusting Image Display:**
- In KLayout: Right-click image → Properties
- Adjust brightness, contrast, transparency
- Change z-order (stacking)

**Layer Management:**
- Show/hide GDS layers as needed
- Adjust layer colors for contrast
- Use layer toolbox (F4 in KLayout)

---

## Troubleshooting

### Program Won't Launch

**Issue**: Double-clicking PointAlign.exe does nothing

**Solutions:**
1. **Try running from command prompt**:
   ```
   cd path\to\PointAlign.exe
   PointAlign.exe
   ```
   (Shows error messages if any)

2. **Install Visual C++ Redistributable**:
   - Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Install and restart

3. **Check Windows Event Viewer**:
   - Search "Event Viewer" in Windows
   - Look under "Application" logs

4. **Antivirus Blocking**:
   - Add exception for PointAlign.exe
   - Some antivirus flags PyInstaller executables

### Template Files Not Found

**Issue**: "Template .lys not found" error

**Solution:**
- Ensure `Test_with_img.lys` and `Test.GDS` are in same folder as PointAlign.exe
- Or manually browse to your own template files

### Point Picker Doesn't Open

**Issue**: Clicked "Run Alignment" but no picker window

**Check:**
1. Did you add images?
2. Did you select output folder/file?
3. Did you select .lys template?
4. Did you select GDS file?

**All required fields must be filled!**

### Poor Alignment Quality (High RMS)

**Issue**: RMS error > 2 µm, images misaligned

**Causes & Fixes:**

1. **Wrong point order**
   - Solution: Redo alignment, follow TL→TR→BL→BR order

2. **Imprecise clicking**
   - Solution: Zoom in MORE before clicking

3. **Wrong GDS coordinates**
   - Solution: Verify coordinates in GDS layout

4. **Image distortion**
   - Solution: Try perspective transform instead of affine

5. **Bad alignment marks**
   - Solution: Use different features or better images

### Images Don't Appear in KLayout

**Issue**: Opened .lys in KLayout, but no images visible

**Check:**

1. **Image files moved/deleted?**
   - .lys stores file paths
   - If images moved, KLayout can't find them
   - Solution: Keep images in original location

2. **Image hidden behind GDS?**
   - Solution: In KLayout, adjust z-order or layer transparency

3. **Zoom/Pan issue?**
   - Solution: Press Shift+F in KLayout to fit view

### Cannot Save .lys File

**Issue**: "Save failed" error

**Solutions:**
1. **File is read-only**
   - Right-click file → Properties → Uncheck "Read-only"

2. **File is open in KLayout**
   - Close KLayout first
   - Then save in Point Align

3. **Permission denied**
   - Save to a different location (e.g., Desktop)

### Slow Performance

**Issue**: Program runs slowly

**Solutions:**
1. **Large images**: Reduce image resolution before import
2. **Too many images**: Process in smaller batches
3. **Insufficient RAM**: Close other programs
4. **Old computer**: Consider upgrading hardware

---

## Technical Details

### Coordinate System

**GDS Coordinates:**
- Units: Micrometers (µm)
- Origin: Chip center (typically)
- Coordinate system defined in GDS file

**Image Coordinates:**
- Units: Pixels
- Origin: Top-left corner of image
- Y-axis increases downward (image convention)

**Transform Matrix:**
- 3x3 homography matrix
- Maps image pixels → GDS micrometers
- Stored in .lys file for each image

### Transformation Types

**Affine Transform:**
- 6 degrees of freedom
- Preserves parallel lines
- Allows: translation, rotation, scaling, shearing
- **Use when**: Standard microscope images

**Perspective Transform:**
- 8 degrees of freedom
- Does NOT preserve parallel lines
- Allows: perspective distortion
- **Use when**: Tilted sample or off-axis imaging

### File Formats

**.lys Format:**
- XML-based text file
- Human-readable (can be edited in text editor)
- Contains session settings for KLayout

**GDS Format:**
- Binary format for chip layouts
- Industry standard (GDSII)
- Also supports OASIS format

### Performance

**Typical Processing Time:**
- Point selection: ~10-30 seconds per image
- Transform calculation: < 1 second per image
- .lys file creation: < 1 second

**Memory Usage:**
- Base program: ~50-100 MB
- Per image: ~image file size + processing overhead
- Large batches (100+ images): May need 4+ GB RAM

### Dependencies (Bundled)

All dependencies are included in PointAlign.exe:

- **Python 3.13**: Programming language
- **PySide6 (Qt)**: GUI framework
- **NumPy**: Numerical computations
- **OpenCV**: Image processing and transforms
- **All libraries**: Bundled, no installation needed

---

## Support & Resources

### Getting Help

**For technical issues:**
1. Check Troubleshooting section above
2. Review error messages carefully
3. Try on a different computer if possible

**For feature requests or bug reports:**
- Contact your program administrator
- Provide screenshots and error messages

### Learning More

**Understanding Transformations:**
- Read about homography and perspective transforms
- OpenCV documentation on geometric transforms

**GDS File Format:**
- GDSII specification
- OASIS format specification

---

## Appendix A: Keyboard Shortcuts

### Align Tab
- *No shortcuts currently*

### LYS Editor Tab
- **Ctrl+S**: Save
- **Ctrl+Shift+S**: Save As
- **Delete**: Delete selected images
- **Alt+Up**: Move selected images up
- **Alt+Down**: Move selected images down
- **F2**: Rename selected image (disabled in current version)

### Point Picker Window
- **Mouse Wheel**: Zoom in/out
- **Left-Click**: Select point
- **Right-Click**: Reset zoom
- **Click + Drag**: Pan image

---

## Appendix B: File Locations

### Program Files

**Executable:**
- `PointAlign.exe` (wherever you placed it)

**Configuration:**
- `align_gui_prefs.json` (same folder as exe)
- `align_tab_prefs.json` (same folder as exe)

**Templates:**
- `Test_with_img.lys` (bundled in exe)
- `Test.GDS` (bundled in exe)

### User Data

**Sessions:**
- `lys_sessions/` folder (created automatically)
- Default save location for new .lys files

**Backups:**
- `lys_sessions/backups/` folder
- Automatic backups of edited .lys files

**Temporary Files:**
- Windows TEMP folder (auto-cleaned by OS)
- Used during .lys creation

---

## Appendix C: Common Coordinate Patterns

### Standard PW Group Coordinates (Default)

```
Top-Left:     (-50, 60) µm
Top-Right:    (70, 60) µm
Bottom-Left:  (-50, -60) µm
Bottom-Right: (70, -60) µm
```

**Pattern Dimensions:**
- Width: 120 µm
- Height: 120 µm
- Centered approximately at (10, 0)

### Custom Coordinate Examples

**Centered Square (100 µm):**
```
Top-Left:     (-50, 50)
Top-Right:    (50, 50)
Bottom-Left:  (-50, -50)
Bottom-Right: (50, -50)
```

**Larger Area (200 µm):**
```
Top-Left:     (-100, 100)
Top-Right:    (100, 100)
Bottom-Left:  (-100, -100)
Bottom-Right: (100, -100)
```

**Offset Pattern:**
```
Top-Left:     (0, 100)
Top-Right:    (100, 100)
Bottom-Left:  (0, 0)
Bottom-Right: (100, 0)
```

---

## Appendix D: Version History

### Version 1.0 (Current)
- Initial release
- Affine and perspective transforms
- Dual-mode LYS editor
- Batch image processing
- Auto-review with RMS quality metrics
- Standalone executable (no Python needed)

---

---

*End of User Manual*

