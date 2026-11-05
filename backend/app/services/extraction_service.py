import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from app.config import settings
from app.utils.logging_utils import logger

class ExtractionError(Exception):
    pass

def run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(cmd)}\nStderr: {e.stderr}")
        raise ExtractionError(f"Command execution error: {e.stderr.strip() or e.stdout.strip()}")

def extract_metadata(video_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    res = run_cmd(cmd)
    data = json.loads(res.stdout)
    
    format_info = data.get("format", {})
    streams = data.get("streams", [])
    
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    
    duration = float(format_info.get("duration", 0.0))
    if duration == 0.0 and video_stream:
        duration = float(video_stream.get("duration", 0.0))

    width = video_stream.get("width") if video_stream else None
    height = video_stream.get("height") if video_stream else None
    
    # Calculate FPS
    fps = 0.0
    if video_stream and "r_frame_rate" in video_stream:
        r_fr = video_stream["r_frame_rate"].split('/')
        if len(r_fr) == 2 and float(r_fr[1]) != 0:
            fps = float(r_fr[0]) / float(r_fr[1])

    metadata = {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "video_codec": video_stream.get("codec_name") if video_stream else None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "has_audio": audio_stream is not None,
        "format_name": format_info.get("format_name")
    }
    return metadata

def validate_video(video_path: str) -> Dict[str, Any]:
    if not os.path.exists(video_path):
        raise ExtractionError("Video file does not exist")
    
    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise ExtractionError(f"File size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB")

    try:
        metadata = extract_metadata(video_path)
    except Exception as e:
        raise ExtractionError(f"Corrupted or invalid video file: {str(e)}")

    if not metadata.get("video_codec"):
        raise ExtractionError("File contains no valid video stream")

    if not metadata.get("has_audio"):
        raise ExtractionError("File contains no audio stream. Original audio is required for accessibility description.")

    if metadata["duration"] > settings.MAX_VIDEO_DURATION_SECONDS:
        raise ExtractionError(f"Video duration ({metadata['duration']:.1f}s) exceeds maximum allowed limit of {settings.MAX_VIDEO_DURATION_SECONDS}s")

    return metadata

def extract_audio(video_path: str, output_path: str, sample_rate: int = 16000) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        output_path
    ]
    run_cmd(cmd)
    return output_path

def extract_frames(video_path: str, output_dir: str, fps: float = 2.0) -> List[Dict[str, Any]]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_pattern = os.path.join(output_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "3",
        out_pattern
    ]
    run_cmd(cmd)
    
    frames = []
    for f in sorted(Path(output_dir).glob("frame_*.jpg")):
        idx = int(f.stem.split("_")[1])
        timestamp = (idx - 1) / fps
        frames.append({
            "frame_idx": idx,
            "timestamp": round(timestamp, 2),
            "file_path": str(f.resolve())
        })
    return frames

