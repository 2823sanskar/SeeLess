"""
spatial_service.py
-------------------
Spatial relationship analysis.

Determines relative positions of people and objects within a scene:
left/right, front/back, near/far, above/below. Provides structured
spatial context for grounded audio descriptions.
"""

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.config import settings
from app.utils.logging_utils import logger


class SpatialError(Exception):
    pass


def _estimate_depth_proxy(bbox: Tuple[int, int, int, int], frame_height: int) -> str:
    """Estimate relative depth from bounding box height (perspective cue)."""
    _, _, _, h = bbox
    relative = h / frame_height if frame_height else 0.0
    if relative > 0.5:
        return "foreground"
    if relative > 0.25:
        return "midground"
    return "background"


def _horizontal_relation(
    a: Tuple[int, int, int, int],
    b: Tuple[int, int, int, int],
) -> str:
    """Return left/right relation between two bounding boxes."""
    a_left, a_right = a[0], a[0] + a[2]
    b_left, b_right = b[0], b[0] + b[2]
    if a_right < b_left - 10:
        return "to the left of"
    if b_right < a_left - 10:
        return "to the right of"
    return "next to"


def _vertical_relation(
    a: Tuple[int, int, int, int],
    b: Tuple[int, int, int, int],
) -> str:
    """Return above/below relation between two bounding boxes."""
    a_center = a[1] + a[3] / 2
    b_center = b[1] + b[3] / 2
    if a_center < b_center - 10:
        return "above"
    if a_center > b_center + 10:
        return "below"
    return "at the same level"


def _detect_objects(frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Detect object bounding boxes via contour analysis."""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 20 and h > 20 and w * h > 400:
                boxes.append((x, y, w, h))
        return boxes
    except Exception:
        return []


def analyze_spatial_relationships(
    frames: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Analyze spatial relationships between detected objects across frames.

    Returns list of {timestamp, objects: [{bbox, depth, relation_to_other}]}.
    """
    if not frames:
        return []

    results: List[Dict[str, Any]] = []
    for f in frames:
        try:
            img = cv2.imread(f["file_path"])
            if img is None:
                continue
        except Exception:
            continue

        h, w = img.shape[:2]
        boxes = _detect_objects(img)
        if len(boxes) < 2:
            continue

        objects = []
        for i, box in enumerate(boxes):
            depth = _estimate_depth_proxy(box, h)
            relations = {}
            for j, other in enumerate(boxes):
                if i == j:
                    continue
                rel_key = f"object_{j}"
                relations[rel_key] = {
                    "horizontal": _horizontal_relation(box, other),
                    "vertical": _vertical_relation(box, other),
                }
            objects.append({
                "bbox": list(box),
                "depth": depth,
                "relations": relations,
            })

        results.append({
            "timestamp": f["timestamp"],
            "object_count": len(objects),
            "objects": objects,
            "frame_idx": f.get("frame_idx", 0),
        })

    logger.info(f"Spatial analysis: {len(results)} frames with multi-object scenes")
    return results