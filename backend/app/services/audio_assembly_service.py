import os
from pathlib import Path
from typing import List, Dict, Any
from app.utils.logging_utils import logger
from app.services.extraction_service import run_cmd, extract_metadata

class AudioAssemblyError(Exception):
    pass

def create_separate_description_track(
    narration_clips: List[Dict[str, Any]],
    output_audio_path: str,
    total_duration: float
) -> str:
    """
    Creates a standalone audio track containing solely the audio description narrations placed at their scheduled timestamps against silence.
    """
    Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)
    
    if not narration_clips:
        # Generate silence of total duration
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(total_duration),
            "-acodec", "pcm_s16le",
            output_audio_path
        ]
        run_cmd(cmd)
        return output_audio_path

    # Construct ffmpeg filter complex for placing clips at scheduled start times
    # Input 0 is silence of total_duration
    inputs = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration}"
    ]
    
    filter_parts = []
    for idx, clip in enumerate(narration_clips):
        clip_path = clip["file_path"]
        delay_ms = int(clip["scheduled_start"] * 1000)
        inputs.extend(["-i", clip_path])
        # [idx+1:a]adelay=delay_ms|delay_ms[a_idx]
        filter_parts.append(f"[{idx+1}:a]adelay={delay_ms}|{delay_ms}[a{idx+1}]")
        
    mix_inputs = "".join([f"[a{i+1}]" for i in range(len(narration_clips))])
    # Amix with base silence
    filter_parts.append(f"[0:a]{mix_inputs}amix=inputs={len(narration_clips)+1}:duration=first:dropout_transition=0[outa]")
    
    cmd = inputs + ["-filter_complex", ";".join(filter_parts), "-map", "[outa]", "-acodec", "pcm_s16le", output_audio_path]
    run_cmd(cmd)
    return output_audio_path

def assemble_audio(
    original_audio_path: str,
    narration_clips: List[Dict[str, Any]],
    output_audio_path: str,
    total_duration: float
) -> str:
    """
    Combines original audio soundtrack with narration clips at scheduled timestamps.
    Original dialogue is preserved without distortion or replacement.
    """
    Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)

    if not narration_clips:
        # Just copy/convert original audio
        cmd = [
            "ffmpeg", "-y",
            "-i", original_audio_path,
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            output_audio_path
        ]
        run_cmd(cmd)
        return output_audio_path

    # Build filter complex to mix narration clips into original audio
    # Input 0: original audio
    inputs = [
        "ffmpeg", "-y",
        "-i", original_audio_path
    ]

    filter_parts = []
    for idx, clip in enumerate(narration_clips):
        clip_path = clip["file_path"]
        delay_ms = int(clip["scheduled_start"] * 1000)
        inputs.extend(["-i", clip_path])
        filter_parts.append(f"[{idx+1}:a]adelay={delay_ms}|{delay_ms},volume=1.0[delayed{idx+1}]")

    delayed_tracks = "".join([f"[delayed{i+1}]" for i in range(len(narration_clips))])
    # Mix original audio with all delayed narration tracks
    filter_parts.append(f"[0:a]{delayed_tracks}amix=inputs={len(narration_clips)+1}:duration=first:dropout_transition=2[outa]")

    cmd = inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[outa]",
        "-acodec", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        output_audio_path
    ]
    run_cmd(cmd)
    return output_audio_path

def create_accessible_video(
    original_video_path: str,
    mixed_audio_path: str,
    output_video_path: str
) -> str:
    """
    Muxes the original video stream with the newly mixed accessible audio stream.
    """
    Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", original_video_path,
        "-i", mixed_audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_video_path
    ]
    run_cmd(cmd)
    return output_video_path

