# klayout_point_align/transforms.py
from __future__ import annotations
from typing import Sequence, Tuple, List
import numpy as np
import math

def solve_affine_px_to_um(pxs: Sequence[Tuple[float, float]],
                          ums: Sequence[Tuple[float, float]]) -> np.ndarray:
    """
    Least-squares affine fit from pixel coords -> microns.
    Requires >= 3 correspondences.
    Returns 3x3 homogeneous transform matrix.
    """
    if len(pxs) != len(ums) or len(pxs) < 3:
        raise ValueError("Affine fit needs >=3 correspondences and equal lengths.")
    A = []
    b = []
    for (x, y), (X, Y) in zip(pxs, ums):
        A.append([x, y, 1, 0, 0, 0])
        A.append([0, 0, 0, x, y, 1])
        b.append(X); b.append(Y)
    A = np.asarray(A, float)
    b = np.asarray(b, float)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    a, b_, c, d, e, f = sol
    H = np.array([[a, b_, c],
                  [d, e, f],
                  [0, 0, 1]], float)
    return H

def solve_proj_px_to_um(pxs: Sequence[Tuple[float, float]],
                        ums: Sequence[Tuple[float, float]]) -> np.ndarray:
    """
    Direct Linear Transform (DLT) projective fit from pixel coords -> microns.
    Requires exactly 4 correspondences.
    Returns 3x3 homogeneous transform matrix (normalized to H[2,2]=1).
    """
    if len(pxs) != len(ums) or len(pxs) != 4:
        raise ValueError("Projective fit needs exactly 4 correspondences.")
    A = []
    for (x, y), (X, Y) in zip(pxs, ums):
        A.append([x, y, 1, 0, 0, 0, -X*x, -X*y, -X])
        A.append([0, 0, 0, x, y, 1, -Y*x, -Y*y, -Y])
    A = np.asarray(A, float)
    U, S, Vt = np.linalg.svd(A)
    h = Vt[-1, :]
    H = h.reshape(3, 3)
    if abs(H[2, 2]) > 1e-12:
        H = H / H[2, 2]
    return H

def build_H_px_to_um(pxs: Sequence[Tuple[float, float]],
                     ums: Sequence[Tuple[float, float]],
                     affine_only: bool) -> np.ndarray:
    return solve_affine_px_to_um(pxs, ums) if affine_only else solve_proj_px_to_um(pxs, ums)

def map_px_to_um(H: np.ndarray, x: float, y: float) -> Tuple[float, float]:
    X, Y, W = H @ np.array([x, y, 1.0], float)
    return (X / W, Y / W)

def rms_um(H: np.ndarray,
           pxs: Sequence[Tuple[float, float]],
           ums: Sequence[Tuple[float, float]]) -> float:
    s = 0.0
    for (x, y), (Xg, Yg) in zip(pxs, ums):
        Xp, Yp = map_px_to_um(H, x, y)
        s += (Xp - Xg) ** 2 + (Yp - Yg) ** 2
    return math.sqrt(s / max(1, len(ums)))

def sort_four_corners(pts: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Sort 4 arbitrary points into canonical corner order: [TL, TR, BL, BR].

    Algorithm:
    1. Find centroid of the 4 points
    2. Classify each point by quadrant relative to centroid
    3. Return in order: top-left, top-right, bottom-left, bottom-right

    Args:
        pts: Exactly 4 (x, y) coordinate tuples in any order

    Returns:
        List of 4 points in order: [top-left, top-right, bottom-left, bottom-right]

    Raises:
        ValueError: If not exactly 4 points provided
    """
    if len(pts) != 4:
        raise ValueError(f"Expected exactly 4 points, got {len(pts)}")

    # Calculate centroid
    cx = sum(x for x, y in pts) / 4.0
    cy = sum(y for x, y in pts) / 4.0

    # Classify points by quadrant
    top_left = None
    top_right = None
    bottom_left = None
    bottom_right = None

    for x, y in pts:
        if x < cx and y < cy:  # Top-left (in image coordinates, y increases downward)
            top_left = (x, y)
        elif x >= cx and y < cy:  # Top-right
            top_right = (x, y)
        elif x < cx and y >= cy:  # Bottom-left
            bottom_left = (x, y)
        else:  # x >= cx and y >= cy  # Bottom-right
            bottom_right = (x, y)

    # Verify we found all 4 corners
    if None in (top_left, top_right, bottom_left, bottom_right):
        # Fallback: if points are collinear or degenerate, use distance-based sorting
        # Sort by y first (top to bottom), then by x (left to right)
        sorted_pts = sorted(pts, key=lambda p: (p[1], p[0]))
        # Top two points (smaller y)
        top_two = sorted(sorted_pts[:2], key=lambda p: p[0])
        # Bottom two points (larger y)
        bottom_two = sorted(sorted_pts[2:], key=lambda p: p[0])
        return [top_two[0], top_two[1], bottom_two[0], bottom_two[1]]

    return [top_left, top_right, bottom_left, bottom_right]
