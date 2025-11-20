# Alignment Metadata in .LYS Files

## Overview

Starting with version 1.2, PointAlign saves detailed alignment metadata directly in `.lys` files. This allows you to review the exact alignment points and settings used for each image, even after the alignment is complete.

## What Gets Saved

Each time you align an image, the following metadata is automatically saved in the `.lys` file:

1. **Picked Points (Centered Pixel Coordinates)** - The 4 points you clicked on the microscope image
2. **Target Points (Micrometers)** - The 4 target coordinates you specified in the GUI
3. **RMS Error (Micrometers)** - The alignment quality measurement
4. **Transformation Type** - Whether affine or projective transformation was used
5. **Timestamp** - When the alignment was performed

## Example Metadata

Here's what the metadata looks like in a `.lys` file:

```xml
<annotation>
  <class>img::Object</class>
  <value>color:matrix=...; file='...'</value>
  <alignment_metadata>
    <timestamp>2025-11-11T13:54:10.037988</timestamp>
    <picked_points_px_centered>
      <point>[-407.5,486.2]</point>
      <point>[567.3,486.1]</point>
      <point>[-407.4,-486]</point>
      <point>[567.5,-486.3]</point>
    </picked_points_px_centered>
    <target_points_um>
      <point>[-50,60]</point>
      <point>[70,60]</point>
      <point>[-50,-60]</point>
      <point>[70,-60]</point>
    </target_points_um>
    <rms_error_um>0.234567</rms_error_um>
    <affine_only>true</affine_only>
  </alignment_metadata>
</annotation>
```

## How to View Metadata

### Option 1: Open .LYS File in Text Editor

1. Navigate to your output `.lys` file
2. Open with any text editor (Notepad, VS Code, etc.)
3. Search for `<alignment_metadata>`
4. You'll see all the alignment details

### Option 2: Parse with Python

```python
import xml.etree.ElementTree as ET

# Load .lys file
tree = ET.parse('output.lys')
root = tree.getroot()

# Find metadata
for annotation in root.iter('annotation'):
    metadata = annotation.find('alignment_metadata')
    if metadata is not None:
        # Extract data
        timestamp = metadata.find('timestamp').text
        rms = metadata.find('rms_error_um').text
        affine = metadata.find('affine_only').text

        print(f"Alignment timestamp: {timestamp}")
        print(f"RMS error: {rms} µm")
        print(f"Affine transformation: {affine}")

        # Get picked points
        picked = metadata.find('picked_points_px_centered')
        for point in picked.findall('point'):
            print(f"Picked: {point.text}")
```

## Understanding the Coordinate Systems

### Picked Points (Centered Pixel Coordinates)

- **Origin**: Center of the image
- **X-axis**: Right is positive
- **Y-axis**: Up is positive
- **Units**: Pixels

Example: `[-407.5, 486.2]` means 407.5 pixels left and 486.2 pixels up from image center

### Target Points (Micrometers)

- **Origin**: Typically (0, 0) at the center of your GDS design
- **X-axis**: Right is positive
- **Y-axis**: Up is positive
- **Units**: Micrometers (µm)

Example: `[-50, 60]` means 50 µm left and 60 µm up from the origin

## Point Order

The 4 points are always stored in this order:
1. **Top-Left (TL)**
2. **Top-Right (TR)**
3. **Bottom-Left (BL)**
4. **Bottom-Right (BR)**

## RMS Error

The RMS (Root Mean Square) error measures alignment quality in micrometers:

- **< 0.5 µm**: Excellent alignment (default threshold)
- **0.5 - 1.0 µm**: Good alignment
- **> 1.0 µm**: May need re-alignment or adjustment

Lower RMS values indicate better alignment accuracy.

## Transformation Types

### Affine Only (affine_only=true)

- Preserves parallel lines
- Allows: translation, rotation, scaling, shearing
- **Recommended** for most microscope alignments
- More stable with measurement noise

### Projective (affine_only=false)

- Allows perspective distortion
- More flexible but can be unstable
- Use only when affine transformation is insufficient

## Use Cases

### 1. Quality Assurance

Review RMS errors across multiple alignments to ensure consistency:

```python
# Check all alignments in a .lys file
for annotation in root.iter('annotation'):
    metadata = annotation.find('alignment_metadata')
    if metadata:
        rms = float(metadata.find('rms_error_um').text)
        if rms > 0.5:
            print(f"Warning: High RMS error: {rms} µm")
```

### 2. Reproducibility

Share `.lys` files with colleagues - they can see exactly which points you picked and verify your alignment.

### 3. Troubleshooting

If an alignment looks wrong in KLayout, check the metadata:
- Are the picked points in the right order?
- Is the RMS error suspiciously high?
- Did you use affine or projective transformation?

### 4. Batch Analysis

Analyze alignment quality across many samples:

```python
import glob

rms_values = []
for lys_file in glob.glob('*.lys'):
    tree = ET.parse(lys_file)
    for annotation in tree.getroot().iter('annotation'):
        metadata = annotation.find('alignment_metadata')
        if metadata:
            rms = float(metadata.find('rms_error_um').text)
            rms_values.append(rms)

print(f"Average RMS: {sum(rms_values)/len(rms_values):.3f} µm")
print(f"Max RMS: {max(rms_values):.3f} µm")
```

## Backward Compatibility

`.lys` files created with older versions of PointAlign (< 1.2) will **not** have this metadata. The alignment will still work in KLayout, but you won't be able to review the original alignment parameters.

New `.lys` files with metadata are fully compatible with KLayout - the metadata is stored in a custom XML element that KLayout ignores.

## Technical Details

### File Location

Metadata is stored as a child element of each `<annotation>` with class `img::Object`:

```
<session>
  <view>
    <annotations>
      <annotation>
        <class>img::Object</class>
        <value>...</value>
        <alignment_metadata>
          <!-- Metadata here -->
        </alignment_metadata>
      </annotation>
    </annotations>
  </view>
</session>
```

### Implementation

The metadata is added by:
- `klayout_point_align/lys_io.py`: `update_klayout_session()` function
- `klayout_point_align/aligner.py`: `align_markers()` passes data to lys_io

### Precision

All floating-point values are stored with 12 significant digits (`{value:.12g}`) to maintain maximum precision.

## FAQ

**Q: Does this slow down the alignment process?**
A: No, the overhead is negligible (< 1ms).

**Q: Can I disable metadata saving?**
A: Not through the GUI, but you can modify the code in `aligner.py` to pass `None` for the metadata parameters.

**Q: Will KLayout still open .lys files with metadata?**
A: Yes! KLayout ignores unknown XML elements, so the metadata has no effect on KLayout's functionality.

**Q: Can I edit the metadata manually?**
A: Yes, since it's just XML. But be careful to maintain valid XML syntax.

**Q: What if I only have the .lys file but not the original microscope image?**
A: The metadata still tells you what points were picked and what the alignment quality was, even if you can't view the original image.

## See Also

- `tests/test_metadata.py` - Unit tests for metadata functionality
- `test_metadata_example.py` - Script to generate example .lys with metadata
- `klayout_point_align/lys_io.py` - Implementation details
