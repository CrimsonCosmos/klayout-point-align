# klayout_point_align/lys_io.py
from __future__ import annotations
from pathlib import Path
from typing import Sequence, Tuple
import xml.etree.ElementTree as ET
import numpy as np

_Z_COUNTER = 0

def reset_z_counter() -> None:
    """Reset the z_position counter used for stacking img::Object annotations."""
    global _Z_COUNTER
    _Z_COUNTER = 0

def build_klayout_img_value(H_um_from_px: np.ndarray,
                            image_file: str,
                            px_tl_tr_br_bl: Sequence[Tuple[float, float]]) -> str:
    """
    Build the value string for an 'img::Object' annotation in a .lys file.
    Matches the format used in your existing sessions.
    """
    H = np.asarray(H_um_from_px, dtype=float)
    def row(i): return f"({H[i,0]:.12g},{H[i,1]:.12g},{H[i,2]:.12g})"
    matrix_str = f"{row(0)} {row(1)} {row(2)}"
    (tlx,tly), (trx,try_), (brx,bry), (blx,bly) = px_tl_tr_br_bl
    landmarks = f"[{tlx:.12g},{tly:.12g},{trx:.12g},{try_:.12g},{brx:.12g},{bry:.12g},{blx:.12g},{bly:.12g}]"
    # Escape backslashes when a Windows style path is embedded
    if ':' in image_file and '\\' in image_file:
        img_path = image_file.replace('\\', '\\\\')
    else:
        img_path = image_file

    global _Z_COUNTER
    _Z_COUNTER += 1
    return (
        f"color:matrix={matrix_str};"
        f"min_value=0;max_value=255;"
        f"is_visible=true;z_position={_Z_COUNTER};"
        f"brightness=0;contrast=0;gamma=1;"
        f"red_gain=1;green_gain=1;blue_gain=1;"
        f"landmarks={landmarks};"
        f"color_mapping=[0,'#000000';1,'#ffffff';];"
        f"file='{img_path}'"
    )

def update_klayout_session(lys_in: str, lys_out: str,
                           image_file: str,
                           H_um_from_px: np.ndarray,
                           px_tl_tr_br_bl: Sequence[Tuple[float, float]],
                           gds_file: str | None = None) -> None:
    """
    Load a .lys file, ensure <annotations> exists, append an 'img::Object'.
    If gds_file is provided, also update <layout>/<file-path> and <layout>/<name>.
    """
    xml_text = Path(lys_in).read_text(encoding="utf-8")
    root = ET.fromstring(xml_text)

    # (1) Optional: update <layout> with a new GDS path
    if gds_file:
        for el in root.iter("layout"):
            fp = None
            name_el = None
            for child in el:
                if child.tag == "file-path":
                    fp = child
                elif child.tag == "name":
                    name_el = child
            if fp is None:
                fp = ET.SubElement(el, "file-path")
            fp.text = str(gds_file)
            base = Path(gds_file).name
            if name_el is None:
                name_el = ET.SubElement(el, "name")
            name_el.text = base
            break  # assume single <layout>

    # (2) Append image annotation in <view>/<annotations>
    view = None
    for el in root.iter():
        if el.tag == "view":
            view = el
            break
    if view is None:
        raise RuntimeError("No <view> element found in LYS.")

    anns = None
    for el in view:
        if el.tag == "annotations":
            anns = el
            break
    if anns is None:
        anns = ET.SubElement(view, "annotations")

    ann = ET.SubElement(anns, "annotation")
    ET.SubElement(ann, "class").text = "img::Object"
    val = ET.SubElement(ann, "value")
    val.text = build_klayout_img_value(H_um_from_px, Path(image_file).as_posix(), px_tl_tr_br_bl)

    Path(lys_out).write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
