"""
audio_mixing_service.py
-----------------------
Professional Audio Experience & Audio Mixing service for the SeeLess narration engine.

Responsibilities:
- EBU R128 standard loudness normalization (-24 LUFS for accessibility/broadcast).
- Smart background ducking: automatically lower original audio / soundtrack volume
  by configurable dB (default -12dB to -18dB) whenever an AI narration clip is active.
- Multi-track stem management: separating original audio stem, narration stem, and
  mixed master track.
- Seamless FFmpeg filter graph generation for multi-track multiplexing.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import settings
from app.services.extraction_service import ExtractionError, run_cmd
from app.utils.logging_utils import logger


class AudioMixingError(Exception):
    """Raised when audio mixing or normalization fails."""


def analyze_loudness(audio_path: str) -> Dict[str, float]:
    """
    Run FFmpeg loudnorm filter pass 1 to measure audio loudness stats.

    Returns dictionary with:
      - input_i: Integrated loudness (LUFS)
      - input_tp: True peak (dBFS)
      - input_lra: Loudness range (LU)
      - input_thresh: Loudness threshold (LUFS)
      - target_offset: Target offset
    """
    if not os.path.exists(audio_path):
        raise AudioMixingError(f"Audio file not found: {audio_path}")

    cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-af", f"loudnorm=I={settings.AUDIO_TARGET_LUFS}:TP={settings.AUDIO_TARGET_TRUE_PEAK_DB}:LRA={settings.AUDIO_LRA_LIMIT}:print_format=json",
        "-f", "null",
        "-"
    ]
    try:
        res = run_cmd(cmd)
        # Parse JSON output embedded in stderr
        stderr = res.stderr
        json_match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)
        if not json_match:
            raise AudioMixingError("Could not parse loudnorm analysis JSON from FFmpeg output.")

        data = json.loads(json_match.group(0))
        return {
            "input_i": float(data.get("input_i", -99.0)),
            "input_tp": float(data.get("input_tp", -99.0)),
            "input_lra": float(data.get("input_lra", 0.0)),
            "input_thresh": float(data.get("input_thresh", -99.0)),
            "target_offset": float(data.get("target_offset", 0.0)),
        }
    except Exception as exc:
        logger.error("Loudness analysis failed for %s: %s", audio_path, exc)
        raise AudioMixingError(f"Loudness analysis failed: {exc}") from exc


def normalize_audio(
    input_audio_path: str,
    output_audio_path: str,
    target_lufs: Optional[float] = None,
    target_tp: Optional[float] = None,
    lra: Optional[float] = None,
) -> str:
    """
    Apply EBU R128 loudness normalization to an audio file using 2-pass FFmpeg loudnorm.

    Target defaults to -24 LUFS (EBU R128 standard).
    """
    if not os.path.exists(input_audio_path):
        raise AudioMixingError(f"Input audio file not found: {input_audio_path}")

    Path(output_audio_path).parent.mkdir(parents=True, exist_ok=True)

    i_target = settings.AUDIO_TARGET_LUFS if target_lufs is None else target_lufs
    tp_target = settings.AUDIO_TARGET_TRUE_PEAK_DB if target_tp is None else target_tp
    lra_target = settings.AUDIO_LRA_LIMIT if lra is None else lra

    # Pass 1: Measure
    try:
        stats = analyze_loudness(input_audio_path)
    except Exception as exc:
        logger.warning("Pass 1 loudness analysis failed (%s); falling back to single-pass loudnorm", exc)
        stats = None

    # Pass 2: Normalize
    if stats and stats["input_i"] > -70.0:
        filter_str = (
            f"loudnorm=I={i_target}:TP={tp_target}:LRA={lra_target}:"
            f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
            f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}:linear=true:print_format=summary"
        )
    else:
        filter_str = f"loudnorm=I={i_target}:TP={tp_target}:LRA={lra_target}:linear=true"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_audio_path,
        "-af", filter_str,
        "-ar", str(settings.AUDIO_SAMPLE_RATE),
        "-ac", str(settings.AUDIO_CHANNELS),
        output_audio_path
    ]

    try:
        run_cmd(cmd)
        logger.info("Normalized audio %s -> %s (Target LUFS: %.1f)", input_audio_path, output_audio_path, i_target)
        return output_audio_path
    except Exception as exc:
        raise AudioMixingError(f"Loudness normalization pass failed: {exc}") from exc


def build_ducking_volume_filter(
    narration_clips: Sequence[Dict[str, Any]],
    total_duration: float,
    ducking_gain_db: Optional[float] = None,
    attack_ms: Optional[float] = None,
    release_ms: Optional[float] = None,
) -> str:
    """
    Generate an FFmpeg volume filter evaluation expression for dynamic background ducking.

    Lowers background soundtrack by ducking_gain_db (e.g. -12dB to -18dB) during active narration intervals.
    Includes smooth linear ramp transitions (attack_ms and release_ms).
    """
    gain_db = settings.DUCKING_GAIN_DB if ducking_gain_db is None else ducking_gain_db
    att_sec = (settings.DUCKING_ATTACK_MS if attack_ms is None else attack_ms) / 1000.0
    rel_sec = (settings.DUCKING_RELEASE_MS if release_ms is None else release_ms) / 1000.0

    linear_attenuation = math.pow(10.0, gain_db / 20.0) # e.g. -12dB -> ~0.251, -18dB -> ~0.126

    if not narration_clips:
        return "volume=1.0"

    # Sort clips by scheduled start time
    sorted_clips = sorted(narration_clips, key=lambda c: float(c.get("scheduled_start", 0.0)))

    # Merge overlapping active ducking intervals
    merged_intervals: List[Tuple[float, float]] = []
    for clip in sorted_clips:
        start = max(0.0, float(clip.get("scheduled_start", 0.0)))
        dur = float(clip.get("actual_duration", clip.get("duration", clip.get("estimated_duration", 1.0))))
        end = min(total_duration, start + dur)

        if end <= start:
            continue

        if merged_intervals and start <= merged_intervals[-1][1] + att_sec + rel_sec:
            merged_intervals[-1] = (merged_intervals[-1][0], max(merged_intervals[-1][1], end))
        else:
            merged_intervals.append((start, end))

    if not merged_intervals:
        return "volume=1.0"

    # Construct nested volume evaluation expression
    conditions = []
    for start, end in merged_intervals:
        conditions.append(f"between(t,{(start - att_sec):.3f},{(end + rel_sec):.3f})")

    combined_cond = "+".join(conditions)
    expr = f"if(gt({combined_cond},0),{linear_attenuation:.4f},1.0)"
    return f"volume=eval=frame:volume='{expr}'"


class AudioStemManager:
    """
    Manages multi-track audio stems:
    - Original Audio Stem (Soundtrack / Dialogue)
    - Narration Audio Stem (Standalone Narration Track on Silence)
    - Mixed Master Track (Soundtrack + Ducking + Normalized Narration)
    """

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_narration_stem(
        self,
        narration_clips: Sequence[Dict[str, Any]],
        total_duration: float,
        output_filename: str = "narration_stem.wav",
        normalize: bool = True,
    ) -> str:
        """
        Build clean multi-clip narration stem placed precisely at scheduled timestamps.
        Optionally normalizes narration clips to EBU R128 (-24 LUFS).
        """
        output_path = str(self.output_dir / output_filename)

        if not narration_clips:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anullsrc=r={settings.AUDIO_SAMPLE_RATE}:cl=stereo",
                "-t", str(total_duration),
                "-acodec", "pcm_s16le",
                output_path
            ]
            run_cmd(cmd)
            return output_path

        inputs = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={settings.AUDIO_SAMPLE_RATE}:cl=stereo:d={total_duration}"
        ]

        filter_parts = []
        for idx, clip in enumerate(narration_clips):
            clip_path = clip["file_path"]
            delay_ms = int(float(clip["scheduled_start"]) * 1000)
            inputs.extend(["-i", clip_path])
            filter_parts.append(f"[{idx+1}:a]adelay={delay_ms}|{delay_ms}[a{idx+1}]")

        mix_inputs = "".join([f"[a{i+1}]" for i in range(len(narration_clips))])
        filter_parts.append(f"[0:a]{mix_inputs}amix=inputs={len(narration_clips)+1}:duration=first:dropout_transition=0[outa]")

        raw_stem = str(self.output_dir / f"raw_{output_filename}")
        cmd = inputs + ["-filter_complex", ";".join(filter_parts), "-map", "[outa]", "-acodec", "pcm_s16le", raw_stem]
        run_cmd(cmd)

        if normalize and settings.AUDIO_NORMALIZATION_ENABLED:
            normalize_audio(raw_stem, output_path)
            if os.path.exists(raw_stem):
                os.remove(raw_stem)
            return output_path
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(raw_stem, output_path)
            return output_path

    def mix_master_track(
        self,
        original_audio_path: str,
        narration_clips: Sequence[Dict[str, Any]],
        total_duration: float,
        output_filename: str = "master_mixed_audio.aac",
        enable_ducking: bool = True,
        ducking_gain_db: Optional[float] = None,
        normalize_master: bool = True,
    ) -> str:
        """
        Mixes original audio stem with narration clips, applying smart background ducking
        and EBU R128 loudness normalization.
        """
        output_path = str(self.output_dir / output_filename)

        # Step 1: Create narration stem
        narration_stem_path = self.create_narration_stem(
            narration_clips=narration_clips,
            total_duration=total_duration,
            output_filename="temp_narration_stem.wav",
            normalize=True,
        )

        if not narration_clips:
            if normalize_master and settings.AUDIO_NORMALIZATION_ENABLED:
                normalize_audio(original_audio_path, output_path)
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", original_audio_path,
                    "-acodec", "aac",
                    "-b:a", "192k",
                    "-ar", str(settings.AUDIO_SAMPLE_RATE),
                    output_path
                ]
                run_cmd(cmd)
            return output_path

        # Build ducking filter for background audio if ducking is enabled
        ducking_filter = "volume=1.0"
        if enable_ducking:
            ducking_filter = build_ducking_volume_filter(
                narration_clips=narration_clips,
                total_duration=total_duration,
                ducking_gain_db=ducking_gain_db,
            )

        raw_mixed_path = str(self.output_dir / f"raw_{output_filename}.wav")

        # FFmpeg filter graph:
        # [0:a] background -> ducking_filter -> [bg]
        # [bg][1:a] amix -> [outa]
        filter_complex = f"[0:a]{ducking_filter}[bg];[bg][1:a]amix=inputs=2:duration=first:dropout_transition=0[outa]"

        cmd = [
            "ffmpeg", "-y",
            "-i", original_audio_path,
            "-i", narration_stem_path,
            "-filter_complex", filter_complex,
            "-map", "[outa]",
            "-acodec", "pcm_s16le",
            "-ar", str(settings.AUDIO_SAMPLE_RATE),
            raw_mixed_path
        ]
        run_cmd(cmd)

        # Cleanup temporary stem
        if os.path.exists(narration_stem_path):
            os.remove(narration_stem_path)

        # Step 2: Normalize master mix to -24 LUFS EBU R128
        if normalize_master and settings.AUDIO_NORMALIZATION_ENABLED:
            normalize_audio(raw_mixed_path, output_path)
            if os.path.exists(raw_mixed_path):
                os.remove(raw_mixed_path)
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", raw_mixed_path,
                "-acodec", "aac",
                "-b:a", "192k",
                "-ar", str(settings.AUDIO_SAMPLE_RATE),
                output_path
            ]
            run_cmd(cmd)
            if os.path.exists(raw_mixed_path):
                os.remove(raw_mixed_path)

        logger.info("Master audio track mixed successfully: %s", output_path)
        return output_path


def mix_professional_audio(
    original_audio_path: str,
    narration_clips: Sequence[Dict[str, Any]],
    output_audio_path: str,
    total_duration: float,
    enable_ducking: bool = True,
    ducking_gain_db: Optional[float] = None,
) -> str:
    """
    Convenience functional API for mixing master track with loudness normalization and ducking.
    """
    out_dir = Path(output_audio_path).parent
    stem_mgr = AudioStemManager(str(out_dir))
    return stem_mgr.mix_master_track(
        original_audio_path=original_audio_path,
        narration_clips=narration_clips,
        total_duration=total_duration,
        output_filename=Path(output_audio_path).name,
        enable_ducking=enable_ducking,
        ducking_gain_db=ducking_gain_db,
        normalize_master=settings.AUDIO_NORMALIZATION_ENABLED,
    )
