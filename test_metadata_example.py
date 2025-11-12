"""
Generate an example .lys file with metadata to show the format.
"""
from pathlib import Path
from klayout_point_align.lys_io import update_klayout_session
import numpy as np

# Create test transformation matrix
H = np.array([
    [0.1234567890, 0.0, -50.0],
    [0.0, 0.1234567890, 60.0],
    [0.0, 0.0, 1.0]
])

# Test data
image_file = "example_microscope_image.jpg"
px_corners = [(-50.0, 60.0), (70.0, 60.0), (70.0, -60.0), (-50.0, -60.0)]
picked_points = [(-407.5, 486.2), (567.3, 486.1), (-407.4, -486.0), (567.5, -486.3)]
target_points = [(-50.0, 60.0), (70.0, 60.0), (-50.0, -60.0), (70.0, -60.0)]
rms_error = 0.234567
affine_only = True

# Create output file
template_lys = Path("Test_with_img.lys")
output_lys = Path("example_with_metadata.lys")

if template_lys.exists():
    update_klayout_session(
        str(template_lys),
        str(output_lys),
        image_file,
        H,
        px_corners,
        gds_file="Test.GDS",
        picked_points_px=picked_points,
        target_points_um=target_points,
        rms_error_um=rms_error,
        affine_only=affine_only
    )

    print(f"Created example .lys file: {output_lys}")
    print("\nMetadata section:")

    # Read and print just the metadata section
    import xml.etree.ElementTree as ET
    tree = ET.parse(output_lys)
    root = tree.getroot()

    for annotation in root.iter('annotation'):
        metadata = annotation.find('alignment_metadata')
        if metadata is not None:
            # Pretty print the metadata
            ET.indent(metadata, space="  ")
            print(ET.tostring(metadata, encoding='unicode'))
            break
else:
    print(f"Error: Template file {template_lys} not found")
