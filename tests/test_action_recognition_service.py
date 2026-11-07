"""
tests/test_action_recognition_service.py
----------------------------------------
Unit tests for action recognition service.
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

import pytest
import numpy as np
import cv2

from app.services.action_recognition_service import (
    _compute_optical_flow,
    _classify_motion,
    _detect_gesture,
    recognize_actions,
    summarize_actions,
    ActionRecognitionError,
)


class TestComputeOpticalFlow:
    """Tests for optical flow computation."""

    def test_identical_frames_returns_zero(self):
        frame = np.zeros((180, 320), dtype=np.uint8)
        flow = _compute_optical_flow(frame, frame)
        assert np.allclose(flow, 0.0)

    def test_shifted_frame_returns_nonzero(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        b[50:100, 50:100] = 255
        flow = _compute_optical_flow(a, b)
        assert np.mean(flow) > 0.0

    def test_none_input_returns_zero(self):
        flow = _compute_optical_flow(None, np.zeros((180, 320)))
        assert np.allclose(flow, 0.0)
        flow = _compute_optical_flow(np.zeros((180, 320)), None)
        assert np.allclose(flow, 0.0)


class TestClassifyMotion:
    """Tests for motion classification."""

    def test_zero_magnitude_is_stationary(self):
        mag = np.zeros((10, 10))
        assert _classify_motion(mag) == "stationary"

    def test_low_magnitude_is_subtle(self):
        mag = np.full((10, 10), 1.0)
        assert _classify_motion(mag) == "subtle_movement"

    def test_medium_magnitude_is_walking(self):
        mag = np.full((10, 10), 5.0)
        assert _classify_motion(mag) == "walking"

    def test_high_magnitude_is_active(self):
        mag = np.full((10, 10), 10.0)
        assert _classify_motion(mag) == "active_movement"

    def test_very_high_magnitude_is_rapid(self):
        mag = np.full((10, 10), 20.0)
        assert _classify_motion(mag) == "rapid_action"


class TestDetectGesture:
    """Tests for gesture detection."""

    def test_upper_motion_detects_arm(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        b[:90, 100:150] = 255  # upper half motion
        gesture = _detect_gesture(a, b)
        assert gesture in ("arm_movement", "hand_gesture")

    def test_no_gesture_returns_none(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        assert _detect_gesture(a, b) is None


class TestRecognizeActions:
    """Tests for action recognition pipeline."""

    def _make_synthetic_frames(self, count: int, motions: list) -> list:
        frames = []
        for i, motion in enumerate(motions):
            img = np.zeros((180, 320, 3), dtype=np.uint8)
            if motion > 0:
                img[50:100, 50:100] = min(255, int(motion * 255))
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                cv2.imwrite(f.name, img)
                frames.append({
                    "frame_idx": i,
                    "timestamp": i * 0.5,
                    "file_path": f.name,
                })
        return frames

    def test_returns_actions_for_moving_frames(self):
        frames = self._make_synthetic_frames(3, [0.0, 5.0, 10.0])
        try:
            actions = recognize_actions(frames, min_confidence=0.1)
            assert len(actions) >= 1
            for a in actions:
                assert "timestamp" in a
                assert "action" in a
                assert "confidence" in a
        finally:
            for f in frames:
                os.unlink(f["file_path"])

    def test_returns_empty_for_static_frames(self):
        frames = self._make_synthetic_frames(3, [0.0, 0.0, 0.0])
        try:
            actions = recognize_actions(frames, min_confidence=0.5)
            assert len(actions) == 0
        finally:
            for f in frames:
                os.unlink(f["file_path"])

    def test_filters_by_confidence(self):
        frames = self._make_synthetic_frames(3, [0.0, 0.5, 1.0])
        try:
            actions = recognize_actions(frames, min_confidence=0.9)
            # Only high-motion frames should pass
            assert all(a["confidence"] >= 0.9 for a in actions)
        finally:
            for f in frames:
                os.unlink(f["file_path"])


class TestSummarizeActions:
    """Tests for action summarization."""

    def test_merges_consecutive_identical_actions(self):
        actions = [
            {"timestamp": 0.0, "action": "walking", "confidence": 0.8, "end": 1.0},
            {"timestamp": 1.0, "action": "walking", "confidence": 0.9, "end": 2.0},
            {"timestamp": 2.0, "action": "walking", "confidence": 0.7, "end": 3.0},
        ]
        summary = summarize_actions(actions)
        assert len(summary) == 1
        assert summary[0]["action"] == "walking"
        assert summary[0]["confidence"] == 0.9  # max

    def test_separates_different_actions(self):
        actions = [
            {"timestamp": 0.0, "action": "walking", "confidence": 0.8, "end": 1.0},
            {"timestamp": 1.0, "action": "standing", "confidence": 0.5, "end": 2.0},
            {"timestamp": 2.0, "action": "walking", "confidence": 0.8, "end": 3.0},
        ]
        summary = summarize_actions(actions)
        assert len(summary) == 3
        assert summary[0]["action"] == "walking"
        assert summary[1]["action"] == "standing"
        assert summary[2]["action"] == "walking"

    def test_empty_input_returns_empty(self):
        assert summarize_actions([]) == []