#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
point_align_batch_runner_gui.py - Batch helper for klayout_point_align (with GUI picker)

Enhancements in this patched version:
- --combined-out: append ALL selected/transformed images into the SAME .lys for this run
- --auto / --auto-review: enable automatic fiducial detection (falls back to GUI on failure)
- optional tuning flags for auto-detect: --auto-canny, --auto-thr, --auto-c, --auto-morph

Works with:
- klayout_point_align.py (patched to support _AUTO_FLAGS/_AUTO_PARAMS and optional autodetect hook)
- autodetect_fiducials.py (new module with OpenCV-based detection)
"""

import argparse
import os
import sys
import glob
import shutil
from pathlib import Path
from typing import List, Sequence, Optional
import importlib

# ---- Safe imports from your aligner ----
try:
    from klayout_point_align import run_point_alignment, parse_pts, reset_z_counter
except Exception:
    from klayout_point_align import run_point_alignment, parse_pts
    def reset_z_counter():  # noqa: E701
        pass

# ---- Optional GUI file picker ----
def _select_files_via_gui(
    title: str = "Select image files to align",
    initialdir: Optional[str] = None,
    patterns = ("*.jpg","*.jpeg","*.JPG","*.JPEG","*.png","*.PNG","*.tif","*.tiff","*.bmp"),
) -> List[Path]:
    """Open a native file picker (Tkinter) to select multiple image files."""
    try:
        import tkinter as _tk
        from tkinter import filedialog as _fd
        root = _tk.Tk(); root.withdraw()
        ft = [("Image files", " ".join(patterns)), ("All files", "*.*")]
        initialdir = initialdir or str(Path.home() / "Pictures")
        selection = _fd.askopenfilenames(title=title, initialdir=initialdir, filetypes=ft)
        root.update(); root.destroy()
        return [Path(p) for p in selection]
    except Exception as e:
        print(f"[info] GUI picker unavailable ({e}). Paste one path per line (blank to finish):", file=sys.stderr)
        paths: List[Path] = []
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                break
            paths.append(Path(line))
        return paths

# ---- Robust glob/dir expansion ----
def _expand_globs_case_insensitive(patterns: Sequence[str]) -> List[Path]:
    out: List[Path] = []
    for pat in patterns or []:
        p = Path(pat).expanduser()
        if p.is_dir():
            exts = ("*.jpg","*.jpeg","*.png","*.tif","*.tiff","*.bmp",
                    "*.JPG","*.JPEG","*.PNG","*.TIF","*.TIFF","*.BMP")
            for ext in exts:
                out.extend(sorted(p.rglob(ext)))
        else:
            for hit in glob.glob(os.fspath(p), recursive=True):
                out.append(Path(hit))
    seen = set(); uniq: List[Path] = []
    for x in out:
        if x.is_file() and x not in seen:
            uniq.append(x); seen.add(x)
    return uniq

def _collect_images_from_args(ns: argparse.Namespace) -> List[Path]:
    if getattr(ns, "files", None):
        imgs = [Path(f).expanduser() for f in ns.files]
    elif getattr(ns, "glob", None):
        imgs = _expand_globs_case_insensitive(ns.glob)
    else:
        if getattr(ns, "gui", False) or not (getattr(ns, "glob", None) or getattr(ns, "files", None)):
            imgs = _select_files_via_gui(title="Select image files to align",
                                         initialdir=str(Path.home() / "Pictures"))
        else:
            imgs = []
    return [p for p in imgs if p.is_file()]

def main() -> int:
    ap = argparse.ArgumentParser(description="Batch runner for klayout_point_align.run_point_alignment (with GUI option)")

    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--glob", action="append",
                   help="Glob(s) or folder(s). e.g. 'C:/path/*.jpg' 'C:/path/**/*.png' 'C:/images'")
    g.add_argument("--files", nargs="+", help="Explicit list of image files")
    ap.add_argument("--gui", action="store_true", help="Open a file picker (default if no --glob/--files)")

    ap.add_argument("--lys-in", required=True, help="Template .lys containing a <view> node")
    ap.add_argument("--out-dir", help="[Per-image mode] Directory for .lys outputs (default: <image_dir>/aligned_lys)")
    ap.add_argument("--out-suffix", default=".lys", help="[Per-image mode] Output extension (default: .lys)")

    # NEW: combined output mode
    ap.add_argument("--combined-out", help="[Combined mode] Single .lys to accumulate all annotations this run")

    ap.add_argument("--affine", dest="affine_only", action="store_true", help="Use affine transform instead of projective")
    ap.add_argument("--rms-thresh-um", type=float, default=0.5, help="Warn if RMS exceeds this (µm)")

    # REQUIRED by klayout_point_align: AFTER points
    ap.add_argument("--after", required=True, type=parse_pts,
                    help="Target µm points TL,TR,BL,BR e.g. '(-50,60),(70,60),(-50,-60),(70,-60)'")
    ap.add_argument("--origin-um", type=parse_pts,
                    help="Optional single '(ox,oy)' shift (pass one pair). Omit to use module default.")

    # Auto-detect flags
    ap.add_argument("--auto", action="store_true", help="Try automatic detection; fall back to GUI on failure")
    ap.add_argument("--auto-review", action="store_true", help="Auto-detect then open GUI pre-seeded for manual tweak")
    ap.add_argument("--auto-canny", help="Canny low,high (e.g. '60,180')")
    ap.add_argument("--auto-thr", type=int, help="Adaptive threshold block size (odd; e.g. 31)")
    ap.add_argument("--auto-c", type=int, help="Adaptive threshold C offset (e.g. 5)")
    ap.add_argument("--auto-morph", type=int, help="Morphological close iterations (e.g. 2)")

    args = ap.parse_args()

    # Reset z_position counter per run (if provided by the core module)
    try:
        reset_z_counter()
    except Exception:
        pass

    images = _collect_images_from_args(args)
    if not images:
        print("No images selected/found. Use --gui or provide --glob/--files.", file=sys.stderr)
        return 2

    # Configure auto-detect behavior in the core module once per run
    _kpa = importlib.import_module("klayout_point_align")
    setattr(_kpa, "_AUTO_FLAGS", (bool(args.auto or args.auto_review), bool(args.auto_review)))

    try:
        from autodetect_fiducials import AutoParams
        if any(getattr(args, x, None) is not None for x in ("auto_canny","auto_thr","auto_c","auto_morph")):
            canny_low, canny_high = 60, 180
            if args.auto_canny:
                try:
                    c0, c1 = args.auto_canny.split(",")
                    canny_low, canny_high = int(c0), int(c1)
                except Exception:
                    pass
            thr_block = args.auto_thr if args.auto_thr else 31
            thr_c = args.auto_c if args.auto_c else 5
            morph = args.auto_morph if args.auto_morph else 2
            setattr(_kpa, "_AUTO_PARAMS", AutoParams(
                canny_low=canny_low, canny_high=canny_high,
                thr_block=thr_block, thr_c=thr_c, morph_iter=morph
            ))
    except Exception:
        # autodetect_fiducials not available; auto falls back to GUI in core
        pass

    lys_in_path = Path(args.lys_in).expanduser()

    # Combined mode: prepare the target once (fresh for each program run)
    combined_path: Optional[Path] = None
    if args.combined_out:
        combined_path = Path(args.combined_out).expanduser()
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(lys_in_path, combined_path)

    # Parse optional origin
    origin = None
    if args.origin_um:
        if len(args.origin_um) != 1:
            print("--origin-um must be a single '(ox,oy)' pair", file=sys.stderr)
            return 2
        origin = args.origin_um[0]

    ok = 0
    for idx, img in enumerate(images):
        if combined_path:
            # Combined mode: append into the same .lys
            if idx == 0:
                lys_in = str(lys_in_path)      # read template
                lys_out = str(combined_path)   # write combined
            else:
                lys_in = str(combined_path)    # read combined
                lys_out = str(combined_path)   # write combined (append new annotation)
        else:
            # Per-image legacy mode
            if args.out_dir:
                out_dir = Path(args.out_dir).expanduser()
            else:
                out_dir = img.parent / "aligned_lys"
            out_dir.mkdir(parents=True, exist_ok=True)
            lys_in = str(lys_in_path)
            lys_out = str(out_dir / (img.stem + args.out_suffix))

        try:
            ret = run_point_alignment(
                image_path=str(img),
                after_pts_um=args.after,
                affine_only=args.affine_only,
                rms_thresh_um=args.rms_thresh_um,
                origin_um=origin,
                out_json=None,
                lys_in=lys_in,
                lys_out=lys_out,
            )
            if isinstance(ret, tuple) and len(ret) >= 2:
                H, rms = ret[0], ret[1]
            else:
                H, rms = ret, float("nan")
            if combined_path:
                print(f"[OK] {img.name} → {combined_path} (RMS={rms:.3f} µm)")
            else:
                print(f"[OK] {img.name} → {lys_out} (RMS={rms:.3f} µm)")
            ok += 1
        except Exception as e:
            print(f"[FAIL] {img}: {e}", file=sys.stderr)

    if combined_path:
        print(f"Done. Appended {ok}/{len(images)} images into: {combined_path}")
    else:
        print(f"Done. {ok}/{len(images)} images processed.")
    return 0 if ok == len(images) else 1

if __name__ == "__main__":
    raise SystemExit(main())
