# PointAlign User Manual
Version 1.2

---

## How it Works

PointAlign aligns microscope images with GDS layout files. You create sessions, add images, click alignment points, and get a .lys file that opens in KLayout with everything aligned.

In short, it aims to transform images of microscope pictures to remove as much distortion from the image as possible (microscope pictures often have a fish-eye effect).

---

## Quick Start

### 1. Sessions
Each session is a separate `.lys` file with its own set of aligned images.

**Create New Session:** Click "+ New Session"
**Open Existing Session:** Click "Open .LYS" to load a saved file
**Output Location:** All sessions save to Desktop by default (named `Aligned1ByUser.lys`, `Aligned2ByUser.lys`, etc.)

You can have multiple sessions open at once. Each one manages different images.

### 2. Add Images
Click "Add Images" and select your microscope photos (JPG, PNG, TIF, etc.). Each image appears as a row.

### 3. Click Points on Each Image
Select each checkbox on images desired to align (or click Select All), and click "Pick Selected".

By default, click where the L-shaped fiducial marks meet the corner boxes. (See the reference image by clicking the ? button at the bottom of the window.)

After clicking all 4 points, alignment runs automatically.

### 4. Open in KLayout (if desired)
Go to your Desktop and double-click the `.lys` file. Your images are now aligned with the GDS layout.

---

## Landmark Presets

Landmark presets store the GDS coordinates (in micrometers) where your fiducial marks live in the design.

**Default preset:** `(-50,60),(70,60),(-50,-60),(70,-60)` (Top-Left, Top-Right, Bottom-Left, Bottom-Right)

**Add custom preset:**
If you have different points on your .GDS that form a rectangle and are visible on the image, then you can create a Landmark Preset and click for those points on the image instead. Obviously,  more accurate clicks and Landmark reference points will result in a more accurate transformation of the image.

- Scroll down to "Landmark Preset Manager"
- Click "Add New..."
- Enter a name and coordinates in the format: `(x1,y1),(x2,y2),(x3,y3),(x4,y4)`

**Use preset:**
Each image row has a "Landmark Preset" dropdown. Select the preset that matches your GDS layout. Alignment re-runs automatically when you change it.

---

## GDS File Presets

GDS presets let you switch between different layout files.

**Default:** Uses the bundled `Test.GDS` file
**Add custom GDS:** Click "Add New..." in the GDS Preset Manager and select your `.gds` file

Each session can use a different GDS file.

---

## Troubleshooting

**Images don't show in KLayout**
Make sure you didn't move or delete the image files after alignment. The .lys file stores absolute paths.

**Alignment looks wrong**
You probably clicked the wrong points. Use the reference diagram (? button) if you're not sure where to click. If you are using custom landmarks, make sure where you are clicking on the image corresponds with the Landmark coordinates that have been set.

---

*For bugs or questions, contact Pengjie Wang at pengjiew@illinois.edu*
