"""
tests/test_spatial_service.py
------------------------------
Unit tests for spatial relationship analysis service.
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

import pytest
import numpy as np
import cv2

from app.services.spatial_service import (
    _estimate_depth_proxy,
    _horizontal_relation,
    _vertical_relation,
    _detect_objects,
    analyze_spatial_relationships,
    SpatialError,
)


class TestEstimateDepthProxy:
    """Tests for depth estimation from bounding box size."""

    def test_large_box_is_foreground(self):
        bbox = (100, 100, 200, 200)  # large box
        depth = _estimate_depth_proxy(bbox, 180)
        assert depth == "foreground"

    def test_medium_box_is_midground(self):
        bbox = (100, 100, 50, 50)
        depth = _estimate_depth_proxy(bbox, 180)
        assert depth == "midground"

    def test_small_box_is_background(self):
        bbox = (100, 100, 20, 20)
        depth = _estimate_depth_proxy(bbox, 180)
        assert depth == "background"


class TestHorizontalRelation:
    """Tests for left/right spatial relations."""

    def test_left_of(self):
        a = (10, 10, 50, 50)
        b = (100, 10, 50, 50)
        assert _horizontal_relation(a, b) == "to the left of"

    def test_right_of(self):
        a = (100, 10, 50, 50)
        b = (10, 10, 50, 50)
        assert _horizontal_relation(a, b) == "to the right of"

    def test_next_to(self):
        a = (50, 10, 30, 30)
        b = (85, 10, 30, 30)  # within 10px of a's right edge
        assert _horizontal_relation(a, b) == "next to"


class TestVerticalRelation:
    """Tests for above/below spatial relations."""

    def test_above(self):
        a = (10, 10, 50, 50)
        b = (10, 100, 50, 50)
        assert _vertical_relation(a, b) == "above"

    def test_below(self):
        a = (10, 100, 50, 50)
        b = (10, 10, 50, 50)
        assert _vertical_relation(a, b) == "below"

    def test_same_level(self):
        a = (10, 50, 50, 50)
        b = (100, 50, 50, 50)  # same y-center
        assert _vertical_relation(a, b) == "at the same level"


class TestDetectObjects:
    """Tests for object detection via contours."""

    def test_empty_frame_returns_empty(self):
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        boxes = _detect_objects(frame)
        assert boxes == []

    def test_detects_large_rectangles(self):
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        cv2.rectangle(frame, (50, 50), (150, 150), (255, 255, 255), -1)  # 100x100
        cv2.rectangle(frame, (200, 50), (280, 130), (255, 255, 255), -1)  # 80x80
        boxes = _detect_objects(frame)
        assert len(boxes) == 2
        for b in boxes:
            assert b[2] > 20 and b[3] > 20

    def test_ignores_small_noise(self):
        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (160, 90), 5, (255, 255, 255), -1)  # tiny
        boxes = _detect_objects(frame)
        assert len(boxes) == 0


class TestAnalyzeSpatialRelationships:
    """Tests for spatial analysis pipeline."""

    def _make_frame_with_objects(self, count: int) -> str:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img = np.zeros((180, 320, 3), dtype=np.uint8)
            for i in range(count):
                x = 50 + i * 80
                y = 50
                cv2.rectangle(img, (x, y), (x + 50, y + 50), (255, 255, 255), -1)
            cv2.imwrite(f.name, img)
            return f.name

    def test_returns_relationships_for_multi_object_frames(self):
        path = self._make_frame_with_objects(3)
        try:
            frames = [{"frame_idx": 0, "timestamp": 0.0, "file_path": path}]
            results = analyze_spatial_relationships(frames)
            assert len(results) == 1
            r = results[0]
            assert r["object_count"] == 3
            assert len(r["objects"]) == 3
            for obj in r["objects"]:
                assert "bbox" in obj
                assert "depth" in obj
                assert "relations" in obj
                assert len(obj["relations"]) == 2  # relations to other 2 objects
        finally:
            os.unlink(path)

    def test_skips_single_object_frames(self):
        path = self._make_frame_with_objects(1)
        try:
            frames = [{"frame_idx": 0, "timestamp": 0.0, "file_path": path}]
            results = analyze_spatial_relationships(frames)
            assert len(results) == 0
        finally:
            os.unlink(path)

    def test_empty_input_returns_empty(self):
        assert analyze_spatial_relationships([]) == []