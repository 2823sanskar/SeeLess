"""
action_recognition_service.py
------------------------------
Action recognition from frame sequences.

Classifies what people are doing by analyzing motion patterns across
consecutive frames: walking, reaching, turning, gesturing, etc.
"""

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.config import settings
from app.utils.logging_utils import logger


class ActionRecognitionError(Exception):
    pass


def _compute_optical_flow(prev: np.ndarray, curr: np.ndarray) -> np.ndarray:
    """Compute dense optical flow magnitude between two grayscale frames."""
    if prev is None or curr is None:
        return np.zeros((1, 1), dtype=np.float32)
    try:
        p = cv2.resize(prev, (320, 180)).astype(np.float32)
        c = cv2.resize(curr, (320, 180)).astype(np.float32)
        flow = cv2.calcOpticalFlowFarneback(
            p, c, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return mag
    except Exception:
        return np.zeros((1, 1), dtype=np.float32)


def _classify_motion(magnitude: np.ndarray) -> str:
    """Classify motion magnitude into an action label."""
    mean_mag = float(np.mean(magnitude)) if magnitude.size else 0.0
    if mean_mag < 0.5:
        return "stationary"
    if mean_mag < 3.0:
        return "subtle_movement"
    if mean_mag < 8.0:
        return "walking"
    if mean_mag < 15.0:
        return "active_movement"
    return "rapid_action"


def _detect_gesture(frame_a: np.ndarray, frame_b: np.ndarray) -> Optional[str]:
    """Detect simple hand/arm gestures via motion hotspots."""
    if frame_a is None or frame_b is None:
        return None
    try:
        a = cv2.resize(frame_a, (320, 180)).astype(np.float32)
        b = cv2.resize(frame_b, (320, 180)).astype(np.float32)
        diff = cv2.absdiff(a, b)
        # Look for motion in upper half (arms/hands region)
        h, w = diff.shape[:2]
        upper = diff[: h // 2, :]
        if np.mean(upper) > 5.0:
            return "arm_movement"
        return None
    except Exception:
        return None


def recognize_actions(
    frames: List[Dict[str, Any]],
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Recognize actions across a sequence of frames.

    Returns list of {timestamp, action, confidence, motion_magnitude, gesture}.
    """
    min_confidence = min_confidence or settings.ACTION_MIN_CONFIDENCE
    if not frames or len(frames) < 2:
        return []

    actions: List[Dict[str, Any]] = []
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
            mag = _compute_optical_flow(prev_gray, gray)
            mean_mag = float(np.mean(mag)) if mag.size else 0.0
            action_label = _classify_motion(mag)
            gesture = _detect_gesture(prev_gray, gray)

            confidence = min(1.0, mean_mag / 5.0) if mean_mag > 0 else 0.0
            if confidence >= min_confidence and action_label != "stationary":
                actions.append({
                    "timestamp": f["timestamp"],
                    "action": action_label,
                    "confidence": round(confidence, 3),
                    "motion_magnitude": round(mean_mag, 3),
                    "gesture": gesture,
                    "frame_idx": f.get("frame_idx", i),
                })
        prev_gray = gray

    logger.info(f"Action recognition: {len(actions)} actions detected from {len(frames)} frames")
    return actions


def summarize_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge consecutive identical actions into summary entries."""
    if not actions:
        return []
    summary: List[Dict[str, Any]] = []
    current = dict(actions[0])
    for a in actions[1:]:
        if a["action"] == current["action"]:
            current["end"] = a["timestamp"]
            current["confidence"] = max(current["confidence"], a["confidence"])
        else:
            summary.append(current)
            current = dict(a)
    summary.append(current)
    return summary