"""
tests/test_frame_extraction_service.py
--------------------------------------
Unit tests for adaptive frame extraction service.
"""

import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

from app.services.frame_extraction_service import (
    extract_frames_adaptive,
    extract_frames_fixed,
    extract_frames,
    FrameExtractionError,
)


class TestExtractFramesFixed:
    """Tests for fixed-FPS fallback extraction."""

    @patch("app.services.frame_extraction_service._run_cmd")
    def test_extract_frames_fixed_returns_frames(self, mock_run_cmd):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock frame files
            for i in range(1, 4):
                Path(tmpdir) / f"frame_{i:04d}.jpg"
                (Path(tmpdir) / f"frame_{i:04d}.jpg").touch()

            frames = extract_frames_fixed("dummy.mp4", tmpdir, fps=2.0)
            assert len(frames) == 3
            for f in frames:
                assert "frame_idx" in f
                assert "timestamp" in f
                assert "file_path" in f
                assert f["motion_score"] == 0.0
                assert f["is_motion"] is True

    @patch("app.services.frame_extraction_service._run_cmd")
    def test_extract_frames_fixed_empty(self, mock_run_cmd):
        with tempfile.TemporaryDirectory() as tmpdir:
            frames = extract_frames_fixed("dummy.mp4", tmpdir, fps=2.0)
            assert frames == []


class TestExtractFramesAdaptive:
    """Tests for adaptive extraction logic."""

    def _make_video_frames(self, count: int, motions: list) -> tuple:
        """Create synthetic frames with given motion scores."""
        frames = []
        prev = None
        for i, motion in enumerate(motions):
            frame = np.zeros((180, 320), dtype=np.uint8)
            if prev is not None and motion > 0:
                frame[10:50, 10:50] = int(motion * 255)
            frames.append({
                "frame_idx": i,
                "timestamp": i * 0.5,
                "file_path": f"/tmp/frame_{i}.jpg",
                "motion_score": motion,
                "is_motion": motion >= 0.05,
            })
            prev = frame
        return frames

    @patch("app.services.frame_extraction_service.cv2.VideoCapture")
    def test_adaptive_extracts_frames(self, mock_cap):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = lambda x: 30.0 if x == cv2.CAP_PROP_FPS else 90
        mock_cap_instance.read.side_effect = [
            (True, np.zeros((180, 320, 3), dtype=np.uint8)) for _ in range(90)
        ]
        mock_cap.return_value = mock_cap_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.services.frame_extraction_service.cv2.imwrite", return_value=True):
                with patch("app.services.frame_extraction_service.cv2.imread") as mock_imread:
                    mock_imread.return_value = np.zeros((180, 320, 3), dtype=np.uint8)
                    frames = extract_frames_adaptive(
                        "dummy.mp4", tmpdir,
                        fps=2.0,
                        motion_threshold=0.05,
                        max_frames_per_scene=8,
                        min_frames_per_scene=2,
                        motion_window_seconds=1.0,
                    )
        assert len(frames) <= 8

    @patch("app.services.frame_extraction_service.cv2.VideoCapture")
    def test_adaptive_enforces_max_frames(self, mock_cap):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = lambda x: 30.0 if x == cv2.CAP_PROP_FPS else 90
        mock_cap_instance.read.side_effect = [
            (True, np.zeros((180, 320, 3), dtype=np.uint8)) for _ in range(120)
        ]
        mock_cap.return_value = mock_cap_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.services.frame_extraction_service.cv2.imwrite", return_value=True):
                with patch("app.services.frame_extraction_service.cv2.imread") as mock_imread:
                    mock_imread.return_value = np.zeros((180, 320, 3), dtype=np.uint8)
                    frames = extract_frames_adaptive(
                        "dummy.mp4", tmpdir,
                        fps=2.0,
                        max_frames_per_scene=5,
                    )
        assert len(frames) <= 5

    @patch("app.services.frame_extraction_service.cv2.VideoCapture")
    def test_adaptive_ensures_min_frames(self, mock_cap):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = lambda x: 30.0 if x == cv2.CAP_PROP_FPS else 10
        mock_cap_instance.read.side_effect = [
            (True, np.zeros((180, 320, 3), dtype=np.uint8)) for _ in range(10)
        ]
        mock_cap.return_value = mock_cap_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.services.frame_extraction_service.cv2.imwrite", return_value=True):
                with patch("app.services.frame_extraction_service.cv2.imread") as mock_imread:
                    mock_imread.return_value = np.zeros((180, 320, 3), dtype=np.uint8)
                    frames = extract_frames_adaptive(
                        "dummy.mp4", tmpdir,
                        fps=2.0,
                        min_frames_per_scene=4,
                    )
        assert len(frames) >= 4

    @patch("app.services.frame_extraction_service.cv2.VideoCapture")
    def test_adaptive_handles_unopenable_video(self, mock_cap):
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = False
        mock_cap.return_value = mock_cap_instance

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FrameExtractionError):
                extract_frames_adaptive("bad.mp4", tmpdir)


class TestExtractFramesUnified:
    """Tests for the unified extract_frames entry point."""

    @patch("app.services.frame_extraction_service.extract_frames_adaptive")
    def test_uses_adaptive_mode(self, mock_adaptive):
        mock_adaptive.return_value = [{"frame_idx": 1, "timestamp": 0.0}]
        frames = extract_frames("video.mp4", "/tmp/out")
        mock_adaptive.assert_called_once()
        assert len(frames) == 1

    @patch("app.services.frame_extraction_service.extract_frames_adaptive")
    @patch("app.services.frame_extraction_service.extract_frames_fixed")
    def test_falls_back_on_error(self, mock_fixed, mock_adaptive):
        mock_adaptive.side_effect = Exception("adaptive failed")
        mock_fixed.return_value = [{"frame_idx": 1, "timestamp": 0.0, "file_path": "a.jpg", "motion_score": 0.0, "is_motion": True}]
        frames = extract_frames("video.mp4", "/tmp/out")
        mock_fixed.assert_called_once()
        assert len(frames) == 1


# Need to import cv2 for the mock in test_extract_frames_fixed
import cv2