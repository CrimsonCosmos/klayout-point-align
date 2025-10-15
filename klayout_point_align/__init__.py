# klayout_point_align/__init__.py
"""
Unified interface for KLayout Auto Align (modular package).
Exports the same names the original single-file version had.
"""

from .picker import pick_points_gui, ZOOM_STEP
from .lys_io import reset_z_counter
from .aligner import run_point_alignment, align_markers, AlignConfig

# Recreate parse_pts helper for backward compatibility
import ast, argparse
def parse_pts(s: str):
    txt = s.strip()
    if not txt.startswith("["):
        txt = "[" + txt + "]"
    try:
        pts = ast.literal_eval(txt)
        out = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                out.append((float(p[0]), float(p[1])))
            else:
                raise ValueError
        return out
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Could not parse points: {e}")

__all__ = [
    "pick_points_gui",
    "ZOOM_STEP",
    "reset_z_counter",
    "run_point_alignment",
    "align_markers",
    "AlignConfig",
    "parse_pts",
]
