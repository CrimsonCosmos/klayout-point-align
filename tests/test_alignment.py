"""
Test alignment calculations.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from klayout_point_align.transforms import (
    solve_proj_px_to_um,
    solve_affine_px_to_um,
    rms_um
)


def test_identity_homography():
    """Test that identical points give identity transformation"""
    # Four corners of a square - use tuples as the API expects
    pts_img = [(0, 0), (100, 0), (100, 100), (0, 100)]
    pts_gds = [(0, 0), (100, 0), (100, 100), (0, 100)]

    H = solve_proj_px_to_um(pts_img, pts_gds)
    rms = rms_um(H, pts_img, pts_gds)

    # RMS error should be near zero for identical points
    assert rms < 1e-6, f"Expected RMS near 0, got {rms}"

    # Transform should map points back to themselves
    for pt_in, pt_expected in zip(pts_img, pts_gds):
        pt_h = np.array([pt_in[0], pt_in[1], 1.0])
        pt_out_h = H @ pt_h
        pt_out = pt_out_h[:2] / pt_out_h[2]

        diff = np.linalg.norm(pt_out - np.array(pt_expected))
        assert diff < 1e-6, f"Point mismatch: {pt_out} vs {pt_expected}"


def test_identity_affine():
    """Test that identical points give identity affine transformation"""
    pts_img = [(0, 0), (100, 0), (100, 100)]
    pts_gds = [(0, 0), (100, 0), (100, 100)]

    H = solve_affine_px_to_um(pts_img, pts_gds)
    rms = rms_um(H, pts_img, pts_gds)

    # RMS error should be near zero
    assert rms < 1e-6, f"Expected RMS near 0, got {rms}"


def test_translation():
    """Test simple translation"""
    # Square at origin (affine needs 3 points minimum)
    pts_img = [(0, 0), (100, 0), (100, 100)]
    # Same square shifted by (50, 30)
    pts_gds = [(50, 30), (150, 30), (150, 130)]

    H = solve_affine_px_to_um(pts_img, pts_gds)
    rms = rms_um(H, pts_img, pts_gds)

    # Should have low error
    assert rms < 1e-6, f"Translation should be exact, got RMS {rms}"

    # Check transformation of origin
    pt_h = np.array([0, 0, 1.0])
    pt_out_h = H @ pt_h
    pt_out = pt_out_h[:2] / pt_out_h[2]

    expected = np.array([50, 30])
    diff = np.linalg.norm(pt_out - expected)
    assert diff < 1e-6, f"Expected {expected}, got {pt_out}"


def test_scaling():
    """Test scaling transformation"""
    # Unit square (3 points for affine)
    pts_img = [(0, 0), (1, 0), (1, 1)]
    # Scaled by factor of 100
    pts_gds = [(0, 0), (100, 0), (100, 100)]

    H = solve_affine_px_to_um(pts_img, pts_gds)
    rms = rms_um(H, pts_img, pts_gds)

    # Should be exact
    assert rms < 1e-6, f"Scaling should be exact, got RMS {rms}"


def test_parse_pts():
    """Test parsing point coordinate strings"""
    from klayout_point_align import parse_pts

    # Test PW Group default format
    pts_str = "(-50,60),(70,60),(-50,-60),(70,-60)"
    pts = parse_pts(pts_str)

    assert len(pts) == 4
    assert pts[0] == (-50, 60)
    assert pts[1] == (70, 60)
    assert pts[2] == (-50, -60)
    assert pts[3] == (70, -60)


if __name__ == "__main__":
    test_identity_homography()
    print("✓ Identity homography")

    test_identity_affine()
    print("✓ Identity affine")

    test_translation()
    print("✓ Translation")

    test_scaling()
    print("✓ Scaling")

    test_parse_pts()
    print("✓ Parse points")

    print("\nAll alignment tests passed!")
