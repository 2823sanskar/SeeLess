"""
expression_service.py
---------------------
Facial expression and body language detection.

Detects meaningful visible expressions and gestures that convey emotional
or intentional information relevant to audio description.
"""

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.config import settings
from app.utils.logging_utils import logger


class ExpressionError(Exception):
    pass


def _detect_face_regions(frame: np.ndarray) -> List[tuple]:
    """Detect face bounding boxes using Haar cascade."""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
    except Exception:
        return []


def _analyze_expression_region(face_img: np.ndarray) -> str:
    """Classify expression from facial region using texture/edge analysis."""
    try:
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.mean(edges)) / 255.0

        # Simple heuristic: high edge density = active expression (smile/surprise)
        # Low edge density = neutral
        if edge_density > 0.08:
            return "expressive"
        if edge_density > 0.04:
            return "subtle_expression"
        return "neutral"
    except Exception:
        return "unknown"


def _detect_body_gesture(frame: np.ndarray) -> Optional[str]:
    """Detect upper-body gestures via motion in upper half of frame."""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        upper = gray[: h // 2, :]
        edges = cv2.Canny(upper, 50, 150)
        density = float(np.mean(edges)) / 255.0
        if density > 0.02:
            return "raised_arm"
        if density > 0.005:
            return "hand_gesture"
        return None
    except Exception:
        return None


def detect_expressions(
    frames: List[Dict[str, Any]],
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Detect facial expressions and body language across frames.

    Returns list of {timestamp, expression, confidence, face_count, gesture}.
    """
    min_confidence = min_confidence or settings.EXPRESSION_MIN_CONFIDENCE
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

        faces = _detect_face_regions(expression_img := img)
        if not faces:
            continue

        # Analyze each detected face
        face_expressions = []
        for (x, y, w, h) in faces:
            face_roi = img[y : y + h, x : x + w]
            if face_roi.size == 0:
                continue
            expr = _analyze_expression_region(face_roi)
            face_expressions.append(expr)

        gesture = _detect_body_gesture(img)
        dominant = max(set(face_expressions), key=face_expressions.count) if face_expressions else "neutral"

        confidence = 0.8 if dominant != "neutral" else 0.4
        if confidence < min_confidence:
            continue

        results.append({
            "timestamp": f["timestamp"],
            "expression": dominant,
            "confidence": round(confidence, 3),
            "face_count": len(faces),
            "gesture": gesture,
            "frame_idx": f.get("frame_idx", 0),
        })

    logger.info(f"Expression detection: {len(results)} expressive frames from {len(frames)}")
    return results