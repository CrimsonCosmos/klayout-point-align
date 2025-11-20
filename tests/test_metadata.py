"""
Test alignment metadata storage in .lys files.
"""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from klayout_point_align.lys_io import update_klayout_session
import numpy as np


def test_metadata_saved_in_lys():
    """Test that alignment metadata is saved correctly in .lys file"""

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Copy template to temp location
        template_lys = Path("Test_with_img.lys")
        if not template_lys.exists():
            print("Warning: Test_with_img.lys not found, skipping")
            return

        output_lys = tmpdir / "test_output.lys"
        shutil.copy(template_lys, output_lys)

        # Create test data
        H = np.eye(3)  # Identity transformation
        H[0, 0] = 0.5  # Scale factor
        H[1, 1] = 0.5

        image_file = "test_image.jpg"
        px_corners = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        picked_points = [(-50.0, 60.0), (70.0, 60.0), (-50.0, -60.0), (70.0, -60.0)]
        target_points = [(-50.0, 60.0), (70.0, 60.0), (-50.0, -60.0), (70.0, -60.0)]
        rms_error = 0.23456789
        affine_only = True

        # Update .lys file with metadata
        update_klayout_session(
            str(template_lys),
            str(output_lys),
            image_file,
            H,
            px_corners,
            gds_file=None,
            picked_points_px=picked_points,
            target_points_um=target_points,
            rms_error_um=rms_error,
            affine_only=affine_only
        )

        # Parse the output .lys file
        tree = ET.parse(output_lys)
        root = tree.getroot()

        # Find the annotation with metadata
        found_metadata = False
        for annotation in root.iter('annotation'):
            metadata = annotation.find('alignment_metadata')
            if metadata is not None:
                found_metadata = True

                # Check timestamp exists
                timestamp = metadata.find('timestamp')
                assert timestamp is not None, "Timestamp should be present"
                assert timestamp.text is not None, "Timestamp should have text"

                # Check picked points
                picked_elem = metadata.find('picked_points_px_centered')
                assert picked_elem is not None, "Picked points should be present"
                points = picked_elem.findall('point')
                assert len(points) == 4, "Should have 4 picked points"
                assert "[-50" in points[0].text, "First point should contain -50"

                # Check target points
                target_elem = metadata.find('target_points_um')
                assert target_elem is not None, "Target points should be present"
                points = target_elem.findall('point')
                assert len(points) == 4, "Should have 4 target points"

                # Check RMS error
                rms_elem = metadata.find('rms_error_um')
                assert rms_elem is not None, "RMS error should be present"
                assert "0.23" in rms_elem.text, f"RMS error should be ~0.23, got {rms_elem.text}"

                # Check affine flag
                affine_elem = metadata.find('affine_only')
                assert affine_elem is not None, "Affine flag should be present"
                assert affine_elem.text == "true", f"Affine flag should be 'true', got {affine_elem.text}"

                break

        assert found_metadata, "alignment_metadata element should be present in .lys file"


def test_lys_without_metadata_still_works():
    """Test that .lys files can still be created without metadata (backward compatibility)"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        template_lys = Path("Test_with_img.lys")
        if not template_lys.exists():
            print("Warning: Test_with_img.lys not found, skipping")
            return

        output_lys = tmpdir / "test_output_no_metadata.lys"
        shutil.copy(template_lys, output_lys)

        # Create test data (minimal)
        H = np.eye(3)
        image_file = "test_image.jpg"
        px_corners = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]

        # Update .lys file WITHOUT metadata (old behavior)
        update_klayout_session(
            str(template_lys),
            str(output_lys),
            image_file,
            H,
            px_corners,
            gds_file=None
            # No metadata parameters passed
        )

        # Parse the output .lys file
        tree = ET.parse(output_lys)
        root = tree.getroot()

        # Should still work - verify annotation exists
        found_annotation = False
        for annotation in root.iter('annotation'):
            class_elem = annotation.find('class')
            if class_elem is not None and class_elem.text == 'img::Object':
                found_annotation = True

                # Should have value
                value_elem = annotation.find('value')
                assert value_elem is not None, "Value should be present"
                assert "test_image.jpg" in value_elem.text, "Image file should be in value"

                # Should NOT have metadata (since we didn't provide it)
                metadata = annotation.find('alignment_metadata')
                assert metadata is None, "Metadata should NOT be present when not provided"

                break

        assert found_annotation, "img::Object annotation should be present"


if __name__ == "__main__":
    print("Running metadata tests...\n")

    try:
        test_metadata_saved_in_lys()
        print("✓ Metadata saved in .lys file")
    except Exception as e:
        print(f"✗ Metadata test failed: {e}")
        raise

    try:
        test_lys_without_metadata_still_works()
        print("✓ Backward compatibility (no metadata)")
    except Exception as e:
        print(f"✗ Backward compatibility test failed: {e}")
        raise

    print("\nAll metadata tests passed!")
