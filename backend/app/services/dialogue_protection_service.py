"""
dialogue_protection_service.py
-------------------------------
Strict dialogue protection for narration scheduling.

Guarantees that generated narration never overlaps protected speech:

- Applies a configurable safety margin around every transcript segment.
- Validates placements against exact audio timestamps.
- Re-validates after real TTS durations are known and reschedules clips that
  no longer fit, instead of silently allowing an overlap.
- Provides a final zero-overlap gate before audio assembly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import settings
from app.services.scheduler_service import (
    find_available_gap,
    reschedule_with_actual_durations,
    verify_schedule_no_overlap,
)
from app.utils.logging_utils import logger
from app.utils.timestamp_utils import intervals_overlap


class DialogueProtectionError(Exception):
    """Raised when dialogue-safety configuration or input is invalid."""


class DialogueProtectionService:
    """
    Enforces strict dialogue safety for narration clips.

    Responsibilities:
    - Validate that no narration clip overlaps a protected speech interval
    - Apply configurable safety padding around speech segments
    - Re-validate and reschedule after actual TTS durations are known
    - Provide a final zero-overlap verification before assembly
    """

    def __init__(
        self,
        safety_padding_ms: Optional[float] = None,
        max_reschedule_attempts: Optional[int] = None,
        min_gap_seconds: Optional[float] = None,
    ) -> None:
        self.safety_padding_ms = float(
            settings.DIALOGUE_SAFETY_PADDING_MS
            if safety_padding_ms is None
            else safety_padding_ms
        )
        self.max_reschedule_attempts = int(
            settings.DIALOGUE_MAX_RESCHEDULE_ATTEMPTS
            if max_reschedule_attempts is None
            else max_reschedule_attempts
        )
        self.min_gap_seconds = float(
            settings.SCHEDULER_MIN_GAP_SECONDS
            if min_gap_seconds is None
            else min_gap_seconds
        )

    # ------------------------------------------------------------------
    # Intervals
    # ------------------------------------------------------------------

    def _padding_seconds(self) -> float:
        return max(0.0, self.safety_padding_ms) / 1000.0

    def _expand_speech_intervals(
        self,
        speech_intervals: Sequence[Dict[str, float]],
    ) -> List[Tuple[float, float]]:
        """Apply safety padding and merge overlapping speech intervals."""
        padding = self._padding_seconds()
        expanded = [
            (
                max(0.0, float(segment["start"]) - padding),
                float(segment["end"]) + padding,
            )
            for segment in speech_intervals
        ]
        expanded.sort(key=lambda pair: pair[0])

        merged: List[Tuple[float, float]] = []
        for start, end in expanded:
            if merged and start <= merged[-1][1] + 1e-6:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def check_overlap(
        self,
        clip_start: float,
        clip_end: float,
        speech_intervals: Sequence[Dict[str, float]],
    ) -> Tuple[bool, Optional[Tuple[float, float]]]:
        """Return ``(has_overlap, conflicting_interval)`` for one clip."""
        for start, end in self._expand_speech_intervals(speech_intervals):
            if intervals_overlap(clip_start, clip_end, start, end):
                return True, (start, end)
        return False, None

    def validate_clip(
        self,
        scheduled_start: float,
        actual_duration: float,
        speech_intervals: Sequence[Dict[str, float]],
        video_duration: float,
    ) -> Tuple[bool, float, float]:
        """Validate one clip placement using its actual TTS duration."""
        if actual_duration <= 0.0:
            raise DialogueProtectionError("actual_duration must be positive")

        scheduled_end = round(scheduled_start + actual_duration, 2)
        if scheduled_start < 0.0 or scheduled_end > video_duration + 1e-6:
            return False, scheduled_start, scheduled_end

        has_overlap, _ = self.check_overlap(
            scheduled_start, scheduled_end, speech_intervals
        )
        if has_overlap:
            return False, scheduled_start, scheduled_end

        return True, scheduled_start, scheduled_end

    def reschedule_clip(
        self,
        requested_start: float,
        required_duration: float,
        speech_intervals: Sequence[Dict[str, float]],
        scheduled_clips: Sequence[Dict[str, Any]],
        video_duration: float,
        max_delay: Optional[float] = None,
    ) -> Tuple[bool, float, float]:
        """
        Find a safe slot for a clip, avoiding padded speech and existing clips.

        ``speech_intervals`` are raw (unpadded) transcript intervals; padding
        is applied internally from this service's configuration.
        """
        expanded = [
            {"start": start, "end": end}
            for start, end in self._expand_speech_intervals(speech_intervals)
        ]
        return find_available_gap(
            requested_start=requested_start,
            required_duration=required_duration,
            speech_intervals=expanded,
            scheduled_clips=scheduled_clips,
            video_duration=video_duration,
            max_delay=max_delay,
            min_gap=self.min_gap_seconds,
        )

    def validate_all_clips(
        self,
        clips: Sequence[Dict[str, Any]],
        speech_intervals: Sequence[Dict[str, float]],
        video_duration: float,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate every clip after TTS generation.

        Returns ``(valid_clips, invalid_clips)`` with statuses populated.
        """
        valid: List[Dict[str, Any]] = []
        invalid: List[Dict[str, Any]] = []

        for clip in clips:
            start = float(clip.get("scheduled_start", 0.0))
            duration = float(
                clip.get("actual_duration", clip.get("duration", 0.0))
            )
            if duration <= 0.0:
                duration = float(clip.get("estimated_duration", 0.0))
            if duration <= 0.0:
                copy = dict(clip)
                copy["status"] = "INVALID"
                copy["reason"] = "Missing clip duration"
                invalid.append(copy)
                continue

            is_valid, final_start, final_end = self.validate_clip(
                start, duration, speech_intervals, video_duration
            )
            copy = dict(clip)
            copy["scheduled_start"] = final_start
            copy["scheduled_end"] = final_end

            if is_valid:
                copy["status"] = "VALIDATED"
                valid.append(copy)
            else:
                copy["status"] = "INVALID"
                copy["reason"] = "Clip would overlap protected speech or video bounds"
                invalid.append(copy)

        logger.info(
            "Dialogue protection: %d valid, %d invalid of %d clips.",
            len(valid),
            len(invalid),
            len(clips),
        )
        return valid, invalid

    def revalidate_and_reschedule(
        self,
        clips: Sequence[Dict[str, Any]],
        speech_intervals: Sequence[Dict[str, float]],
        video_duration: float,
        max_delay: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Post-TTS loop: reschedule clips whose actual duration no longer fits,
        then assert zero overlap across the final schedule.

        Returns ``{"scheduled": [...], "omitted": [...], "stats": {...}}``.
        """
        result = reschedule_with_actual_durations(
            clips=clips,
            protected_speech_intervals=speech_intervals,
            video_duration=video_duration,
            min_gap=self.min_gap_seconds,
            max_delay=max_delay,
        )
        if not self.verify_zero_overlap(result["scheduled"], speech_intervals):
            raise DialogueProtectionError(
                "Post-TTS reschedule still produced a dialogue overlap"
            )
        return result

    def verify_zero_overlap(
        self,
        clips: Sequence[Dict[str, Any]],
        speech_intervals: Sequence[Dict[str, float]],
    ) -> bool:
        """Final verification that no narration overlaps protected speech."""
        safe = verify_schedule_no_overlap(clips, speech_intervals)
        if safe:
            logger.info("Zero overlap verified: all clips are dialogue-safe.")
        return safe

    def verify_video_bounds(
        self,
        clips: Sequence[Dict[str, Any]],
        video_duration: float,
    ) -> bool:
        """Confirm every clip starts at/after 0 and ends within the video."""
        for clip in clips:
            start = float(clip.get("scheduled_start", 0.0))
            end = float(clip.get("scheduled_end", 0.0))
            if start < 0.0 or end > video_duration + 1e-6 or end <= start:
                logger.error(
                    "Clip bounds violation: [%.2f-%.2f] outside [0, %.2f].",
                    start,
                    end,
                    video_duration,
                )
                return False
        return True
