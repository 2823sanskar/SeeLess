"""
frame_extraction_service.py
---------------------------
Content-aware adaptive frame sampling.

Replaces fixed-FPS sampling with motion- and scene-aware selection so
important visual events are captured without wasting frames on static scenes.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.config import settings
from app.utils.logging_utils import logger


class FrameExtractionError(Exception):
    pass


def _run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
    )


def _detect_motion(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
) -> float:
    """Return mean absolute difference between two grayscale frames (0.0-1.0)."""
    if frame_a is None or frame_b is None:
        return 0.0
    try:
        a = cv2.resize(frame_a, (320, 180))
        b = cv2.resize(frame_b, (320, 180))
        diff = cv2.absdiff(a, b)
        return float(np.mean(diff)) / 255.0
    except Exception:
        return 0.0


def _load_frame(path: str) -> Optional[np.ndarray]:
    try:
        img = cv2.imread(path)
        if img is None:
            return None
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except Exception:
        return None


def extract_frames_adaptive(
    video_path: str,
    output_dir: str,
    fps: Optional[float] = None,
    motion_threshold: Optional[float] = None,
    max_frames_per_scene: Optional[int] = None,
    min_frames_per_scene: Optional[int] = None,
    motion_window_seconds: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Extract frames adaptively: dense sampling during motion, sparse during static scenes.

    Returns list of {frame_idx, timestamp, file_path, motion_score}.
    """
    fps = fps or settings.FRAME_EXTRACTION_FPS
    motion_threshold = motion_threshold or settings.FRAME_ADAPTIVE_MOTION_THRESHOLD
    max_frames_per_scene = max_frames_per_scene or settings.FRAME_ADAPTIVE_MAX_FRAMES_PER_SCENE
    min_frames_per_scene = min_frames_per_scene or settings.FRAME_ADAPTIVE_MIN_FRAMES_PER_SCENE
    motion_window_seconds = motion_window_seconds or settings.FRAME_ADAPTIVE_MOTION_WINDOW_SECONDS

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FrameExtractionError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or fps
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps if video_fps else 0.0

    frame_interval = int(round(video_fps / fps))
    if frame_interval < 1:
        frame_interval = 1

    frames: List[Dict[str, Any]] = []
    prev_gray: Optional[np.ndarray] = None
    frame_idx = 0
    output_idx = 0
    max_reads = total_frames if total_frames > 0 else None

    while max_reads is None or frame_idx < max_reads:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            motion = _detect_motion(prev_gray, gray) if prev_gray is not None else 1.0
            prev_gray = gray

            timestamp = frame_idx / video_fps if video_fps else 0.0
            out_path = os.path.join(output_dir, f"frame_{output_idx:04d}.jpg")
            cv2.imwrite(out_path, frame)

            frames.append({
                "frame_idx": output_idx,
                "timestamp": round(timestamp, 2),
                "file_path": str(Path(out_path).resolve()),
                "motion_score": round(motion, 4),
                "is_motion": motion >= motion_threshold,
            })
            output_idx += 1

        frame_idx += 1

    cap.release()

    if not frames:
        raise FrameExtractionError(f"No frames extracted from {video_path}")

    # Enforce per-scene caps: keep motion frames first, then fill with static
    if len(frames) > max_frames_per_scene:
        motion_frames = [f for f in frames if f["is_motion"]]
        static_frames = [f for f in frames if not f["is_motion"]]
        keep = motion_frames[:max_frames_per_scene]
        remaining = max(0, max_frames_per_scene - len(keep))
        keep.extend(static_frames[:remaining])
        keep.sort(key=lambda f: f["frame_idx"])
        frames = keep

    if len(frames) < min_frames_per_scene and frames:
        # Ensure at least min_frames_per_scene frames
        last = frames[-1]
        while len(frames) < min_frames_per_scene:
            frames.append(dict(last, frame_idx=len(frames)))

    logger.info(
        f"Adaptive extraction: {len(frames)} frames from {duration:.1f}s video "
        f"(motion threshold={motion_threshold})"
    )
    return frames


def extract_frames_fixed(video_path: str, output_dir: str, fps: float = 2.0) -> List[Dict[str, Any]]:
    """Legacy fixed-FPS extraction (fallback mode)."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_pattern = os.path.join(output_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "3",
        out_pattern,
    ]
    _run_cmd(cmd)

    frames = []
    for f in sorted(Path(output_dir).glob("frame_*.jpg")):
        idx = int(f.stem.split("_")[1])
        timestamp = (idx - 1) / fps
        frames.append({
            "frame_idx": idx,
            "timestamp": round(timestamp, 2),
            "file_path": str(f.resolve()),
            "motion_score": 0.0,
            "is_motion": True,
        })
    return frames


def extract_frames(
    video_path: str,
    output_dir: str,
    fps: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Unified entry point. Uses adaptive mode by default; falls back to fixed FPS.
    """
    mode = settings.FRAME_EXTRACTION_MODE.lower()
    if mode == "adaptive":
        try:
            return extract_frames_adaptive(video_path, output_dir, fps=fps)
        except Exception as exc:
            logger.warning(f"Adaptive extraction failed, falling back to fixed FPS: {exc}")
    return extract_frames_fixed(video_path, output_dir, fps=fps or settings.FRAME_EXTRACTION_FPS)