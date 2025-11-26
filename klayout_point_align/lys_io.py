# klayout_point_align/lys_io.py
from __future__ import annotations
from pathlib import Path
from typing import Sequence, Tuple, Optional
import xml.etree.ElementTree as ET
import numpy as np
from datetime import datetime

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

def remove_image_from_lys(root: ET.Element, image_file: str) -> int:
    """
    Remove all img::Object annotations for a specific image file from the LYS XML root.

    Args:
        root: The XML root element of the .lys file
        image_file: Path to the image file to remove

    Returns:
        Number of annotations removed
    """
    removed_count = 0
    # Normalize the image path for comparison (handle both / and \\ separators)
    target_path = Path(image_file).as_posix()

    # Find all annotations
    for view in root.iter("view"):
        anns = None
        for el in view:
            if el.tag == "annotations":
                anns = el
                break

        if anns is None:
            continue

        # Find and remove annotations for this image
        annotations_to_remove = []
        for ann in anns.findall("annotation"):
            class_elem = ann.find("class")
            if class_elem is not None and class_elem.text == "img::Object":
                value_elem = ann.find("value")
                if value_elem is not None and value_elem.text:
                    # Check if this annotation contains the target image file
                    # The value contains: file='path/to/image.jpg'
                    if f"file='{target_path}'" in value_elem.text or \
                       f'file="{target_path}"' in value_elem.text or \
                       target_path.replace('/', '\\\\') in value_elem.text:
                        annotations_to_remove.append(ann)

        # Remove the annotations
        for ann in annotations_to_remove:
            anns.remove(ann)
            removed_count += 1

    return removed_count


def update_klayout_session(lys_in: str, lys_out: str,
                           image_file: str,
                           H_um_from_px: np.ndarray,
                           px_tl_tr_br_bl: Sequence[Tuple[float, float]],
                           gds_file: str | None = None,
                           picked_points_px: Optional[Sequence[Tuple[float, float]]] = None,
                           target_points_um: Optional[Sequence[Tuple[float, float]]] = None,
                           rms_error_um: Optional[float] = None,
                           affine_only: Optional[bool] = None) -> None:
    """
    Load a .lys file, ensure <annotations> exists, append an 'img::Object'.
    If gds_file is provided, also update <layout>/<file-path> and <layout>/<name>.
    Optionally adds alignment metadata as a custom XML element.

    NOTE: If the same image already exists in the file, it will be removed first
    to prevent duplicates when re-aligning with a different GDS preset.
    """
    xml_text = Path(lys_in).read_text(encoding="utf-8")
    root = ET.fromstring(xml_text)

    # Remove any existing annotations for this image file to prevent duplicates
    removed = remove_image_from_lys(root, image_file)
    if removed > 0:
        # Log that we removed duplicates (optional, for debugging)
        pass

    # (1) Optional: update <layout> with a new GDS path
    if gds_file:
        base = Path(gds_file).name
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
            if name_el is None:
                name_el = ET.SubElement(el, "name")
            name_el.text = base
            break  # assume single <layout>

        # Also update the cellview's layout-ref to match the new layout name
        for cellview in root.iter("cellview"):
            for child in cellview:
                if child.tag == "layout-ref":
                    child.text = base
                    break

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

    # Add custom metadata element if alignment data is provided
    if picked_points_px is not None or target_points_um is not None or rms_error_um is not None:
        metadata = ET.SubElement(ann, "alignment_metadata")

        # Timestamp
        ET.SubElement(metadata, "timestamp").text = datetime.now().isoformat()

        # Original picked points (centered pixel coordinates)
        if picked_points_px is not None:
            picked_elem = ET.SubElement(metadata, "picked_points_px_centered")
            for px, py in picked_points_px:
                point_elem = ET.SubElement(picked_elem, "point")
                point_elem.text = f"[{px:.12g},{py:.12g}]"

        # Target points (micrometers)
        if target_points_um is not None:
            target_elem = ET.SubElement(metadata, "target_points_um")
            for ux, uy in target_points_um:
                point_elem = ET.SubElement(target_elem, "point")
                point_elem.text = f"[{ux:.12g},{uy:.12g}]"

        # RMS error
        if rms_error_um is not None:
            ET.SubElement(metadata, "rms_error_um").text = f"{rms_error_um:.12g}"

        # Transformation type
        if affine_only is not None:
            ET.SubElement(metadata, "affine_only").text = str(affine_only).lower()

    Path(lys_out).write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")

def extract_image_paths_from_lys(lys_file: str) -> list[str]:
    """
    Parse a .lys file and extract all image file paths from img::Object annotations.

    Args:
        lys_file: Path to the .lys file

    Returns:
        List of image file paths found in the LYS file
    """
    try:
        xml_text = Path(lys_file).read_text(encoding="utf-8")
        root = ET.fromstring(xml_text)

        image_paths = []

        # Find all annotations with class="img::Object"
        for ann in root.iter("annotation"):
            class_elem = ann.find("class")
            if class_elem is not None and class_elem.text == "img::Object":
                value_elem = ann.find("value")
                if value_elem is not None and value_elem.text:
                    # Parse the value string to extract file path
                    # Format: "...;file='path/to/image.jpg'"
                    value_str = value_elem.text
                    if "file='" in value_str:
                        # Extract path between file=' and the closing '
                        start = value_str.index("file='") + 6
                        end = value_str.index("'", start)
                        file_path = value_str[start:end]
                        # Unescape double backslashes
                        file_path = file_path.replace('\\\\', '\\')
                        image_paths.append(file_path)

        return image_paths
    except Exception as e:
        print(f"Error extracting images from {lys_file}: {e}")
        return []

def extract_alignment_metadata_from_lys(lys_file: str) -> dict[str, str]:
    """
    Parse a .lys file and extract alignment metadata (picked points) for each image.

    Args:
        lys_file: Path to the .lys file

    Returns:
        Dictionary mapping image file paths to coordinate strings in the format:
        "(x1,y1),(x2,y2),(x3,y3),(x4,y4)"
    """
    try:
        xml_text = Path(lys_file).read_text(encoding="utf-8")
        root = ET.fromstring(xml_text)

        metadata_map = {}

        # Find all annotations with class="img::Object"
        for ann in root.iter("annotation"):
            class_elem = ann.find("class")
            if class_elem is not None and class_elem.text == "img::Object":
                # Extract image path
                value_elem = ann.find("value")
                if value_elem is None or not value_elem.text:
                    continue

                value_str = value_elem.text
                if "file='" not in value_str:
                    continue

                start = value_str.index("file='") + 6
                end = value_str.index("'", start)
                file_path = value_str[start:end].replace('\\\\', '\\')

                # Extract picked points from alignment_metadata
                metadata_elem = ann.find("alignment_metadata")
                if metadata_elem is not None:
                    picked_elem = metadata_elem.find("picked_points_px_centered")
                    if picked_elem is not None:
                        points = []
                        for point_elem in picked_elem.findall("point"):
                            if point_elem.text:
                                # Parse "[x,y]" format
                                coords_str = point_elem.text.strip()
                                if coords_str.startswith('[') and coords_str.endswith(']'):
                                    coords_str = coords_str[1:-1]  # Remove brackets
                                    x, y = map(float, coords_str.split(','))
                                    points.append((x, y))

                        # Format as coordinate string: "(x1,y1),(x2,y2),..."
                        if len(points) == 4:
                            coords_str = ",".join(f"({x:.1f},{y:.1f})" for x, y in points)
                            metadata_map[file_path] = coords_str

        return metadata_map
    except Exception as e:
        print(f"Error extracting alignment metadata from {lys_file}: {e}")
        return {}

def flip_image_y_axis_in_lys(lys_file: str, image_path: str) -> bool:
    """
    Flip an image's y-axis in a .lys file by negating the y-transformation
    and swapping top/bottom landmarks.

    Args:
        lys_file: Path to the .lys file to modify
        image_path: Path to the specific image to flip

    Returns:
        True if successful, False otherwise
    """
    try:
        xml_text = Path(lys_file).read_text(encoding="utf-8")
        root = ET.fromstring(xml_text)

        # Normalize image path for comparison
        image_path_normalized = Path(image_path).as_posix()

        # Find the annotation for this specific image
        for ann in root.iter("annotation"):
            class_elem = ann.find("class")
            if class_elem is not None and class_elem.text == "img::Object":
                value_elem = ann.find("value")
                if value_elem is None or not value_elem.text:
                    continue

                value_str = value_elem.text

                # Check if this is the right image
                if "file='" not in value_str:
                    continue

                start = value_str.index("file='") + 6
                end = value_str.index("'", start)
                file_path = value_str[start:end].replace('\\\\', '\\')
                file_path_normalized = Path(file_path).as_posix()

                if file_path_normalized != image_path_normalized:
                    continue

                # Use regex to find and replace specific parts without breaking structure
                import re

                # 1. Find and flip the matrix
                matrix_pattern = r'matrix=\(([^)]+)\)\s+\(([^)]+)\)\s+\(([^)]+)\)'
                matrix_match = re.search(matrix_pattern, value_str)
                if matrix_match:
                    row0_str, row1_str, row2_str = matrix_match.groups()

                    # Parse row 1 (y-transformation)
                    row1 = [float(x) for x in row1_str.split(',')]
                    # Flip y-axis: negate row 1
                    row1_flipped = [-x for x in row1]

                    # Format the flipped row
                    row1_new_str = ','.join(f'{x:.12g}' for x in row1_flipped)

                    # Replace only the second row in the matrix
                    new_matrix = f'matrix=({row0_str}) ({row1_new_str}) ({row2_str})'
                    value_str = value_str[:matrix_match.start()] + new_matrix + value_str[matrix_match.end():]

                # 2. Find and flip the landmarks (swap top<->bottom)
                landmarks_pattern = r'landmarks=\[([^\]]+)\]'
                landmarks_match = re.search(landmarks_pattern, value_str)
                if landmarks_match:
                    coords_str = landmarks_match.group(1)
                    coords = [float(x) for x in coords_str.split(',')]
                    if len(coords) == 8:
                        tlx, tly, trx, try_, brx, bry, blx, bly = coords
                        # Swap top <-> bottom: TL<->BL, TR<->BR
                        new_landmarks = [blx, bly, brx, bry, trx, try_, tlx, tly]
                        new_landmarks_str = ','.join(f'{x:.12g}' for x in new_landmarks)

                        # Replace landmarks
                        new_landmarks_full = f'landmarks=[{new_landmarks_str}]'
                        value_str = value_str[:landmarks_match.start()] + new_landmarks_full + value_str[landmarks_match.end():]

                # Update the XML
                value_elem.text = value_str

                # Save the modified LYS file
                Path(lys_file).write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
                return True

        # Image not found in LYS file
        return False

    except Exception as e:
        print(f"Error flipping image in {lys_file}: {e}")
        import traceback
        traceback.print_exc()
        return False
