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

## Introduction

Point Align aligns microscope images to GDS (GDSII) layout files for viewing in KLayout.

**What it does:**
1. Takes microscope images (JPG, PNG, TIF, etc.)
2. You mark 4 corresponding points on the image and GDS layout
3. Calculates transformation matrix to align them
4. Creates a KLayout session file (.lys) with aligned images

**Use cases:** Failure analysis, process verification, documentation, quality control

---

## Installation

### Standalone Executable (Recommended)
No Python installation required.

1. Download `PointAlign.exe`
2. Double-click to launch

### System Requirements
- Windows 10 or Windows 11 (64-bit)
- 4GB RAM minimum (8GB recommended)
- Optional: KLayout installed to open .lys output files

---

## Main Features

### Align Tab
- Batch process multiple images
- Point-based alignment (affine or homography)
- Automatic GDS coordinate mapping
- RMS error reporting

### LYS Editor Tab
- Edit existing .lys sessions
- Add/remove images
- Change image order (z-stacking)
- Update file paths

---

## Align Tab - Step-by-Step Guide

### Step 1: Load Template Session

Click **"Browse Template .lys..."** and select `Test_with_img.lys` (included with program).

This template contains:
- Default GDS layout
- View settings
- Layer configuration

### Step 2: Add Images

Click **"Add images..."** and select one or more images.

Supported formats: JPEG, PNG, TIFF, BMP, GIF, WebP

### Step 3: Set Output Location

Click **"Browse Folder..."** to choose where the output .lys file will be saved.

### Step 4: Configure GDS File (Optional)

Default: Uses GDS from template .lys

To change: Click **"Browse GDS..."** and select a different .GDS file

### Step 5: Set Alignment Points (GDS Coordinates)

**PW Group Mode (Default):**
Uses standard 4-point pattern at (-50,60), (70,60), (-50,-60), (70,-60) µm

**Custom Mode:**
Enter your own 4 coordinates in µm (X,Y format)

### Step 6: Run Alignment

Click **"Run Alignment"**

**Point Picker Window:**
1. Image displays with zoom/pan controls
2. Click 4 points in order: Top-Left, Top-Right, Bottom-Left, Bottom-Right
3. Use mouse wheel to zoom
4. Right-click and drag to pan
5. Click "Submit Points" when done
6. Or click "Skip Image" to exclude

**Controls:**
- Mouse wheel: Zoom in/out
- Right-click + drag: Pan
- Left-click: Place point

**Alignment Quality (RMS Error):**
- **RMS < 0.5 µm**: Excellent alignment
- **RMS 0.5-2 µm**: Good (acceptable for most use cases)
- **RMS > 2 µm**: Poor (check your points)

### Step 7: View Results

The aligned .lys file is created in your output folder.

To view in KLayout:
1. Locate output .lys file
2. Double-click to open in KLayout
3. Your images appear overlaid on the GDS layout

---

## LYS Editor Tab

Edit existing .lys session files.

### Opening a Session
Click **"Open .lys"** and select a file

### Adding Images
1. Click **"Add Image"**
2. Browse to image file
3. Enter 4 corner coordinates in µm
4. Image added to list

### Editing Images
1. Select image from list
2. Click **"Edit"**
3. Modify path or coordinates
4. Click **"Save"**

### Removing Images
1. Select image from list
2. Click **"Remove"**

### Changing Image Order
- Select image and click **"Move Up"** or **"Move Down"**
- Images stack in KLayout based on list order (z-position)

### Saving Changes
Click **"Save .lys"** to write changes to file

---

## Understanding Output Files

### .lys Files
- KLayout session file (XML format)
- Contains:
  - Image file paths
  - Transformation matrices
  - GDS layout reference
  - KLayout view settings (zoom, layers, etc.)
- Opens directly in KLayout (double-click)

### File Locations
**Default output:** Desktop folder named `Aligned-YYYY-MM-DD-#.lys`

**Session backups:** Saved in `lys_sessions/backups/`

---

## Tips & Best Practices

### Image Preparation
- Use high-resolution images (300+ DPI)
- Ensure alignment marks are clearly visible
- Avoid motion blur or out-of-focus images
- Consistent lighting helps

### Alignment Point Selection

**For best accuracy:**
1. Zoom in before clicking
2. Use sharp, well-defined features (pad corners, via centers, alignment mark crosshairs)
3. Avoid fuzzy/blurry areas
4. Spread points widely - don't cluster them
5. Be consistent across all images

**Common mistakes to avoid:**
- Clicking too quickly without zooming
- Using soft/rounded features
- Selecting points too close together
- Wrong point order

### Batch Processing
1. Add all images at once
2. Point picker processes each sequentially
3. Review RMS errors after completion
4. Re-process any poor alignments

---

## Troubleshooting

### Images Don't Appear in KLayout

**Issue:** Opened .lys in KLayout, but no images visible

**Solutions:**
- Check image file paths are correct
- Verify images weren't moved/deleted after alignment
- Check images aren't hidden behind GDS layers
- Press Shift+F in KLayout to fit view

### Poor Alignment (High RMS Error)

**Causes:**
- Clicked wrong points
- Used wrong point order
- Points too close together
- Blurry/unclear features

**Solutions:**
- Re-run alignment for that image
- Zoom in more when clicking
- Use sharper features as alignment points

### Can't Edit .lys File

**Causes:**
1. File is corrupted
2. File is open in KLayout

**Solutions:**
- Close KLayout first
- Check file is valid XML
- Restore from backup in `lys_sessions/backups/`

### Program Won't Start

**Cause:** Missing Visual C++ Redistributable

**Solution:** Install vc_redist.x64.exe from Microsoft

---

## Technical Details

### Transformation Types

**Affine (Default):**
- Preserves parallel lines
- Allows rotation, scaling, shearing, translation
- 6 degrees of freedom
- Use when: Images are from flat samples with minimal distortion

**Homography:**
- Allows perspective distortion
- 8 degrees of freedom
- Use when: Images have perspective effects or non-flat samples

### Coordinate Systems

**Image Space:** Pixels (top-left origin)

**GDS Space:** Micrometers (center origin)

**Transformation:** Image pixels → GDS micrometers via calculated matrix

### File Format

.lys files are XML-based with structure:
- `<layout-view>`: GDS layout reference
- `<images>`: List of image annotations
- Each image contains path and transformation matrix

---

## Keyboard Shortcuts

**Point Picker:**
- Mouse wheel: Zoom
- Right-click + drag: Pan

**Main Window:**
- Ctrl+O: Open .lys (Editor tab)
- Ctrl+S: Save .lys (Editor tab)

---

## Preferences

Preferences saved in `align_tab_prefs.json`

**Auto-saved settings:**
- Last template .lys path
- Last GDS file path
- Last output folder
- Window size/position

---

## Advanced Features

### Custom Coordinate Entry
Enter coordinates manually instead of using PW Group mode

Format: `(X1,Y1),(X2,Y2),(X3,Y3),(X4,Y4)` in micrometers

### Session Management
- Sessions auto-saved with timestamps
- Backups kept in `lys_sessions/backups/`
- Prevents overwriting existing work

---

*End of User Manual*
