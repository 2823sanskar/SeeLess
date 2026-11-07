"""
tests/test_background_event_service.py
---------------------------------------
Unit tests for background event detection service.
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

import pytest
import numpy as np
import cv2

from app.services.background_event_service import (
    _compute_background_motion,
    _detect_new_object,
    detect_background_events,
    BackgroundEventError,
)


class TestComputeBackgroundMotion:
    """Tests for peripheral motion computation."""

    def test_identical_frames_returns_zero(self):
        frame = np.zeros((180, 320), dtype=np.uint8)
        motion = _compute_background_motion(frame, frame)
        assert motion == 0.0

    def test_motion_in_bands_returns_nonzero(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        # Motion in left peripheral band
        b[:, :64] = 255
        motion = _compute_background_motion(a, b)
        assert motion > 0.0

    def test_center_motion_ignored(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        # Motion only in center (excluded from peripheral bands)
        b[50:130, 100:220] = 255
        motion = _compute_background_motion(a, b)
        assert motion < 0.1  # very small or zero


class TestDetectNewObject:
    """Tests for new object detection in background."""

    def test_high_edge_density_detects_object(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        b[:180, :64] = 255  # high density in left band
        event = _detect_new_object(a, b)
        assert event == "object_appears"

    def test_medium_density_detects_change(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        b[:180, :64] = 100  # medium density
        event = _detect_new_object(a, b)
        assert event == "background_change"

    def test_low_density_returns_none(self):
        a = np.zeros((180, 320), dtype=np.uint8)
        b = np.zeros((180, 320), dtype=np.uint8)
        b[:180, :64] = 20  # very low
        assert _detect_new_object(a, b) is None


class TestDetectBackgroundEvents:
    """Tests for background event detection pipeline."""

    def _make_synthetic_frames(self, count: int, motions: list) -> list:
        frames = []
        for i, motion in enumerate(motions):
            img = np.zeros((180, 320, 3), dtype=np.uint8)
            if motion > 0:
                img[:, :64] = int(motion * 255)  # motion in left band
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                cv2.imwrite(f.name, img)
                frames.append({
                    "frame_idx": i,
                    "timestamp": i * 0.5,
                    "file_path": f.name,
                })
        return frames

    def test_returns_events_for_motion_in_periphery(self):
        frames = self._make_synthetic_frames(3, [0.0, 0.5, 1.0])
        try:
            events = detect_background_events(frames, min_confidence=0.1)
            assert len(events) >= 1
            for e in events:
                assert "timestamp" in e
                assert "event_type" in e
                assert "confidence" in e
                assert "region" in e
        finally:
            for f in frames:
                os.unlink(f["file_path"])

    def test_returns_empty_for_static_frames(self):
        frames = self._make_synthetic_frames(3, [0.0, 0.0, 0.0])
        try:
            events = detect_background_events(frames, min_confidence=0.5)
            assert len(events) == 0
        finally:
            for f in frames:
                os.unlink(f["file_path"])

    def test_filters_by_confidence(self):
        frames = self._make_synthetic_frames(3, [0.0, 0.2, 0.5])
        try:
            events = detect_background_events(frames, min_confidence=0.8)
            assert all(e["confidence"] >= 0.8 for e in events)
        finally:
            for f in frames:
                os.unlink(f["file_path"])

    def test_empty_input_returns_empty(self):
        assert detect_background_events([], min_confidence=0.1) == []