# klayout_point_align/transforms.py
from __future__ import annotations
from typing import Sequence, Tuple
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
