import os
from typing import List, Dict, Any
from app.utils.logging_utils import logger
from app.services.extraction_service import extract_metadata
from app.utils.timestamp_utils import intervals_overlap

class QualityValidationError(Exception):
    pass

def validate_accessible_output(
    video_path: str,
    audio_description_path: str,
    original_duration: float,
    protected_speech_intervals: List[Dict[str, float]],
    scheduled_clips: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Performs comprehensive technical and safety validation on the generated accessible video and audio.
    """
    report = {
        "file_checks": True,
        "timing_checks": True,
        "dialogue_safety_checks": True,
        "errors": []
    }

    # 1. File checks
    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        report["file_checks"] = False
        report["errors"].append("Final accessible video file does not exist or is empty.")

    if not os.path.exists(audio_description_path) or os.path.getsize(audio_description_path) == 0:
        report["file_checks"] = False
        report["errors"].append("Audio description track does not exist or is empty.")

    if not report["file_checks"]:
        raise QualityValidationError("; ".join(report["errors"]))

    # 2. Metadata checks
    meta = extract_metadata(video_path)
    if not meta.get("video_codec"):
        report["file_checks"] = False
        report["errors"].append("Final output is missing a video stream.")

    if not meta.get("has_audio"):
        report["file_checks"] = False
        report["errors"].append("Final output is missing an audio stream.")

    # Duration tolerance (within 2.0 seconds)
    if abs(meta["duration"] - original_duration) > 2.0:
        logger.warning(f"Output duration ({meta['duration']}s) differs slightly from original ({original_duration}s).")

    # 3. Timing and Dialogue Safety checks
    for clip in scheduled_clips:
        start = clip["scheduled_start"]
        end = clip["scheduled_end"]
        if end > original_duration + 0.5:
            report["timing_checks"] = False
            report["errors"].append(f"Clip '{clip.get('text')}' exceeds total video duration ({end}s > {original_duration}s).")

        # Check against speech intervals
        for sp in protected_speech_intervals:
            if intervals_overlap(start, end, sp["start"], sp["end"]):
                report["dialogue_safety_checks"] = False
                report["errors"].append(f"Overlap detected: narration clip '{clip.get('text')}' ({start}s-{end}s) overlaps dialogue ({sp['start']}s-{sp['end']}s).")

    if not report["file_checks"] or not report["timing_checks"] or not report["dialogue_safety_checks"]:
        raise QualityValidationError("; ".join(report["errors"]))

    logger.info("Quality validation passed successfully.")
    return report

