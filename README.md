# 🧭 Klayout Auto-Align (Point Align GUI)

A lightweight PySide6 (Qt) application and toolkit for fiducial-based image alignment and KLayout `.lys` session generation.

Developed by **Wang Lab / University of Illinois**, this utility provides a full GUI interface for batch point-alignment of microscope images using affine or projective transforms.

---

## 🚀 Features
- Aqua-style **Qt GUI** (`align_gui_aqua_qt.py`) with live console output.
- **Batch runner** (`point_align_batch_runner_gui.py`) to process multiple images.
- **Core alignment logic** (`klayout_point_align.py`) combining:
  - 4-point picker GUI  
  - affine / projective transform solvers  
  - automatic `.lys` annotation generation
- Optional **auto-detection** hook for fiducials (`autodetect_fiducials.py` if present).
- Clean PyInstaller build workflow for standalone binaries.

---

## 🧩 Repository structure
