import os
import shutil
import re
from pathlib import Path
from app.config import STORAGE_PATH

def sanitize_filename(filename: str) -> str:
    # Remove unsupported characters
    clean = re.sub(r'[^\w\-_\.]', '_', filename)
    return clean

def get_video_dir(video_id: str) -> Path:
    video_dir = STORAGE_PATH / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    return video_dir

def init_video_storage(video_id: str) -> dict:
    video_dir = get_video_dir(video_id)
    subdirs = ["original", "extracted", "analysis", "descriptions", "narration", "output"]
    paths = {}
    for sub in subdirs:
        p = video_dir / sub
        p.mkdir(parents=True, exist_ok=True)
        paths[sub] = p
    # Also extracted/frames
    frames_dir = paths["extracted"] / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    paths["frames"] = frames_dir
    return paths

