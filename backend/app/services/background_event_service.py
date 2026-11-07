"""
background_event_service.py
----------------------------
Background event detection.

Captures important visual events occurring outside the main subject —
objects entering/leaving, background actions, environmental changes —
that would be missed by focus-on-subject analysis alone.
"""

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.config import settings
from app.utils.logging_utils import logger


class BackgroundEventError(Exception):
    pass


def _compute_background_motion(prev: np.ndarray, curr: np.ndarray) -> float:
    """Motion in peripheral regions (edges of frame) excluding center subject."""
    try:
        a = cv2.resize(prev, (320, 180)).astype(np.float32)
        b = cv2.resize(curr, (320, 180)).astype(np.float32)
        diff = cv2.absdiff(a, b)
        h, w = diff.shape[:2]
        # Peripheral bands: left/right edges, excluding center 60%
        margin = int(w * 0.2)
        bands = np.concatenate([
            diff[:, :margin],
            diff[:, w - margin:],
        ])
        return float(np.mean(bands)) / 255.0
    except Exception:
        return 0.0


def _detect_new_object(prev: np.ndarray, curr: np.ndarray) -> Optional[str]:
    """Detect new objects appearing in background via edge density change."""
    try:
        a = cv2.resize(prev, (160, 90)).astype(np.float32)
        b = cv2.resize(curr, (160, 90)).astype(np.float32)
        diff = cv2.absdiff(a, b)
        h, w = diff.shape[:2]
        margin = int(w * 0.2)
        bands = np.concatenate([diff[:, :margin], diff[:, w - margin:]])
        density = float(np.mean(bands)) / 255.0
        if density > 0.4:
            return "object_appears"
        if density > 0.08:
            return "background_change"
        return None
    except Exception:
        return None


def detect_background_events(
    frames: List[Dict[str, Any]],
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Detect important background events across frames.

    Returns list of {timestamp, event_type, confidence, region, motion_score}.
    """
    min_confidence = min_confidence or settings.BACKGROUND_EVENT_MIN_CONFIDENCE
    if not frames or len(frames) < 2:
        return []

    events: List[Dict[str, Any]] = []
    prev_gray: Optional[np.ndarray] = None

    for i in range(len(frames)):
        f = frames[i]
        try:
            img = cv2.imread(f["file_path"])
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except Exception:
            continue

        if prev_gray is not None:
            motion = _compute_background_motion(prev_gray, gray)
            obj_event = _detect_new_object(prev_gray, gray)

            confidence = min(1.0, motion * 5.0)
            if obj_event:
                obj_confidence = 0.9 if obj_event == "object_appears" else 0.75
                confidence = max(confidence, obj_confidence)
            if confidence < min_confidence:
                prev_gray = gray
                continue

            events.append({
                "timestamp": f["timestamp"],
                "event_type": obj_event or "background_motion",
                "confidence": round(confidence, 3),
                "region": "peripheral",
                "motion_score": round(motion, 4),
                "frame_idx": f.get("frame_idx", i),
            })
        prev_gray = gray

    logger.info(f"Background events: {len(events)} detected from {len(frames)} frames")
    return events