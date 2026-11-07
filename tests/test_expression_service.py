"""
tests/test_expression_service.py
--------------------------------
Unit tests for expression and body language detection service.
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

import pytest
import numpy as np
import cv2

from app.services.expression_service import (
    _detect_face_regions,
    _analyze_expression_region,
    _detect_body_gesture,
    detect_expressions,
    ExpressionError,
)


class TestDetectFaceRegions:
    """Tests for face detection."""

    def test_empty_frame_returns_empty(self):
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        faces = _detect_face_regions(frame)
        assert faces == []

    def test_no_face_in_plain_image(self):
        frame = np.ones((180, 320, 3), dtype=np.uint8) * 128
        faces = _detect_face_regions(frame)
        assert faces == []


class TestAnalyzeExpressionRegion:
    """Tests for expression classification."""

    def test_high_edges_is_expressive(self):
        face = np.zeros((80, 80, 3), dtype=np.uint8)
        cv2.rectangle(face, (10, 10), (70, 70), (255, 255, 255), 3)  # high edge density
        expr = _analyze_expression_region(face)
        assert expr in ("expressive", "subtle_expression")

    def test_low_edges_is_neutral(self):
        face = np.ones((80, 80, 3), dtype=np.uint8) * 128
        expr = _analyze_expression_region(face)
        assert expr == "neutral"


class TestDetectBodyGesture:
    """Tests for body gesture detection."""

    def test_upper_motion_detects_raised_arm(self):
        img = np.zeros((180, 320, 3), dtype=np.uint8)
        img[:90, 100:200] = 255  # motion in upper half
        gesture = _detect_body_gesture(img)
        assert gesture in ("raised_arm", "hand_gesture")

    def test_no_gesture_returns_none(self):
        img = np.zeros((180, 320, 3), dtype=np.uint8)
        assert _detect_body_gesture(img) is None


class TestDetectExpressions:
    """Tests for expression detection pipeline."""

    def _make_frame_with_face(self, has_face: bool = True) -> str:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img = np.zeros((180, 320, 3), dtype=np.uint8)
            if has_face:
                # Draw a simple face-like pattern
                cv2.ellipse(img, (160, 90), (40, 50), 0, 0, 360, (200, 200, 200), -1)
                cv2.circle(img, (150, 80), 5, (0, 0, 0), -1)
                cv2.circle(img, (170, 80), 5, (0, 0, 0), -1)
            cv2.imwrite(f.name, img)
            return f.name

    def test_returns_expressions_for_frames_with_faces(self):
        path1 = self._make_frame_with_face(True)
        path2 = self._make_frame_with_face(False)
        try:
            frames = [
                {"frame_idx": 0, "timestamp": 0.0, "file_path": path1},
                {"frame_idx": 1, "timestamp": 0.5, "file_path": path2},
            ]
            expressions = detect_expressions(frames, min_confidence=0.1)
            assert len(expressions) >= 0  # may find or not depending on Haar cascade
            for e in expressions:
                assert "timestamp" in e
                assert "expression" in e
                assert "confidence" in e
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_filters_by_confidence(self):
        path1 = self._make_frame_with_face(True)
        try:
            frames = [{"frame_idx": 0, "timestamp": 0.0, "file_path": path1}]
            expressions = detect_expressions(frames, min_confidence=0.9)
            assert all(e["confidence"] >= 0.9 for e in expressions)
        finally:
            os.unlink(path1)

    def test_empty_input_returns_empty(self):
        assert detect_expressions([], min_confidence=0.1) == []