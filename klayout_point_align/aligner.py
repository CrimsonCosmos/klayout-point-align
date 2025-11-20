# klayout_point_align/aligner.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Tuple, Optional, List
import numpy as np
from pathlib import Path

from .picker import pick_points_gui
from .transforms import build_H_px_to_um, rms_um
from .lys_io import update_klayout_session

try:
    from .autodetect_bridge import detect_four_points_centered
except Exception:
    detect_four_points_centered = None

_AUTO_FLAGS = (False, False)   # use_auto, auto_review
_AUTO_PARAMS = None

@dataclass
class AlignConfig:
    after_pts_um: Sequence[Tuple[float, float]]
    affine_only: bool = True
    rms_thresh_um: float = 0.5
    after_origin_um: Tuple[float, float] = (0.0, 0.0)

def align_markers(before_ctr_px: Sequence[Tuple[float, float]],
                  cfg: AlignConfig,
                  lys_in: str | None = None,
                  lys_out: str | None = None,
                  image_file: str | None = None,
                  gds_file: str | None = None) -> Tuple[np.ndarray, float]:
    """
    Compute transformation and optionally update .lys session with image annotation.
    """
    ox, oy = cfg.after_origin_um
    after_shifted = [(X + ox, Y + oy) for (X, Y) in cfg.after_pts_um]
    H = build_H_px_to_um(before_ctr_px, after_shifted, cfg.affine_only)
    err = rms_um(H, before_ctr_px, after_shifted)

    if lys_in and lys_out and image_file:
        px_tl_tr_br_bl = [before_ctr_px[0], before_ctr_px[1], before_ctr_px[3], before_ctr_px[2]]
        update_klayout_session(
            lys_in, lys_out, image_file, H, px_tl_tr_br_bl,
            gds_file=gds_file,
            picked_points_px=list(before_ctr_px),
            target_points_um=list(cfg.after_pts_um),
            rms_error_um=err,
            affine_only=cfg.affine_only
        )
    return H, err

def run_point_alignment(image_path: str,
                        after_pts_um: Sequence[Tuple[float, float]],
                        *,
                        affine_only: bool = True,
                        rms_thresh_um: float = 0.5,
                        origin_um: Optional[Tuple[float, float]] = None,
                        out_json: Optional[str] = None,
                        lys_in: Optional[str] = None,
                        lys_out: Optional[str] = None,
                        gds_file: Optional[str] = None) -> Tuple[np.ndarray, float, List[Tuple[float, float]]]:
    """
    Top-level entrypoint for alignment. Launches point picker (or autodetect),
    computes transform, optionally updates .lys file.
    """
    use_auto, auto_review = _AUTO_FLAGS
    pts_cxcy: List[Tuple[float, float]] | None = None

    if use_auto and detect_four_points_centered is not None:
        try:
            pts_cxcy = detect_four_points_centered(image_path, params=_AUTO_PARAMS)
            if auto_review:
                picker = pick_points_gui(image_path, max_points=4)
                pts_cxcy = picker or pts_cxcy
        except Exception:
            pts_cxcy = None

    if not pts_cxcy:
        pts_cxcy = pick_points_gui(image_path, max_points=4)

    if not pts_cxcy:
        raise RuntimeError("No points were picked.")

    cfg = AlignConfig(
        after_pts_um=list(after_pts_um),
        affine_only=affine_only,
        rms_thresh_um=rms_thresh_um,
        after_origin_um=origin_um or (0.0, 0.0),
    )

    H, err = align_markers(
        pts_cxcy,
        cfg,
        lys_in=lys_in,
        lys_out=lys_out,
        image_file=image_path,
        gds_file=gds_file,
    )
    return H, err, pts_cxcy
