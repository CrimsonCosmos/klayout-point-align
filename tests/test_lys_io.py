"""
Test .lys file reading and writing.
"""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent))

from klayout_point_align.lys_io import (
    update_klayout_session,
    build_klayout_img_value
)
import numpy as np


def test_template_lys_exists():
    """Test that template .lys file exists"""
    template_path = Path("Test_with_img.lys")
    assert template_path.exists(), f"Template not found: {template_path}"


def test_template_lys_is_valid_xml():
    """Test that template .lys is valid XML"""
    template_path = Path("Test_with_img.lys")

    try:
        tree = ET.parse(template_path)
        root = tree.getroot()
        assert root is not None
    except ET.ParseError as e:
        assert False, f"Template .lys is not valid XML: {e}"


def test_build_klayout_img_value():
    """Test building KLayout image annotation value string"""
    # Identity transformation matrix (pixels to µm)
    H = np.eye(3)

    # Image file path
    img_file = "test_image.jpg"

    # Four corners in pixel coordinates
    px_corners = [(0, 0), (100, 0), (100, 100), (0, 100)]

    # Build value string
    value = build_klayout_img_value(H, img_file, px_corners)

    # Should be a string
    assert isinstance(value, str)

    # Should contain the image filename
    assert "test_image.jpg" in value or "test_image" in value.replace("\\\\", "")

    # Should contain matrix values
    assert "matrix" in value.lower() or "," in value


def test_gds_file_exists():
    """Test that default GDS file exists"""
    gds_path = Path("Test.GDS")
    assert gds_path.exists(), f"Default GDS not found: {gds_path}"


if __name__ == "__main__":
    test_template_lys_exists()
    print("✓ Template .lys exists")

    test_template_lys_is_valid_xml()
    print("✓ Template .lys is valid XML")

    test_build_klayout_img_value()
    print("✓ Build KLayout image value")

    test_gds_file_exists()
    print("✓ GDS file exists")

    print("\nAll file I/O tests passed!")
