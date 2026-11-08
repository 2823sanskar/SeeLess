"""
scheduler_service.py
---------------------
Narration scheduler for the SeeLess narration engine.

Responsibilities:
- Priority-based placement of narration into gaps between protected dialogue.
- Strict safety padding around every speech interval.
- Automatic shortening and omission when a gap is too constrained.
- Re-verification after real TTS clip durations are known, including
  rescheduling clips that grew beyond their estimated slot.

The scheduler is deterministic: given the same inputs and configuration it
produces the same schedule. It never places narration over protected speech.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import settings
from app.utils.logging_utils import logger
from app.utils.timestamp_utils import intervals_overlap

_EPSILON = 1e-6
_DEFAULT_WORDS_PER_MINUTE = 150.0
_TRAILING_STOPWORDS = frozenset(
    {
        "and", "but", "or", "with", "to", "of", "in", "on", "at", "for",
        "the", "a", "an", "his", "her", "their", "as", "while", "then",
    }
)
_WHITESPACE_RE = re.compile(r"\s+")


class SchedulingError(Exception):
    """Raised when scheduler input is malformed."""


def estimate_speech_duration(
    text: str,
    words_per_minute: float = _DEFAULT_WORDS_PER_MINUTE,
) -> float:
    """Estimate spoken duration (seconds) for a narration sentence."""
    words = len(text.strip().split())
    if words == 0:
        return 1.0
    if words_per_minute <= 0:
        raise SchedulingError("words_per_minute must be positive")
    duration = (words / (words_per_minute / 60.0)) + 0.3
    return max(1.0, round(duration, 2))


def _padding_seconds() -> float:
    return max(0.0, float(settings.DIALOGUE_SAFETY_PADDING_MS)) / 1000.0


def _min_gap_seconds() -> float:
    return max(0.0, float(settings.SCHEDULER_MIN_GAP_SECONDS))


def _max_delay_seconds() -> float:
    return max(0.0, float(settings.SCHEDULER_MAX_DELAY_SECONDS))


def _merge_intervals(
    intervals: Sequence[Tuple[float, float]],
) -> List[Tuple[float, float]]:
    """Merge overlapping/adjacent intervals into a sorted, disjoint list."""
    if not intervals:
        return []
    ordered = sorted(
        (max(0.0, float(start)), float(end)) for start, end in intervals
    )
    merged: List[Tuple[float, float]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + _EPSILON:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _expand_speech_intervals(
    speech_intervals: Sequence[Dict[str, float]],
    video_duration: Optional[float] = None,
) -> List[Dict[str, float]]:
    """Apply the configured safety padding to each speech interval, clamped to video bounds."""
    padding = _padding_seconds()
    expanded: List[Dict[str, float]] = []
    for segment in speech_intervals:
        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SchedulingError(f"Invalid speech interval: {segment!r}") from exc
        clamped_end = (
            min(end + padding, video_duration)
            if video_duration is not None
            else end + padding
        )
        expanded.append(
            {"start": max(0.0, start - padding), "end": clamped_end}
        )
    return expanded


def _occupancy(
    speech_intervals: Sequence[Dict[str, float]],
    scheduled_clips: Sequence[Dict[str, Any]],
) -> List[Tuple[float, float]]:
    """Build merged occupied intervals from speech + placed narration."""
    raw: List[Tuple[float, float]] = [
        (float(segment["start"]), float(segment["end"]))
        for segment in speech_intervals
    ]
    for clip in scheduled_clips:
        raw.append(
            (
                float(clip.get("scheduled_start", 0.0)),
                float(clip.get("scheduled_end", 0.0)),
            )
        )
    return _merge_intervals(raw)


def _too_close(
    start: float,
    end: float,
    other_start: float,
    other_end: float,
    min_gap: float,
) -> bool:
    """True when intervals overlap or are separated by less than ``min_gap``."""
    if intervals_overlap(start, end, other_start, other_end):
        return True
    if min_gap <= 0.0:
        return False
    if end <= other_start + _EPSILON:
        return (other_start - end) < min_gap
    if other_end <= start + _EPSILON:
        return (start - other_end) < min_gap
    return False


def find_available_gap(
    requested_start: float,
    required_duration: float,
    speech_intervals: Sequence[Dict[str, float]],
    scheduled_clips: Sequence[Dict[str, Any]],
    video_duration: float,
    max_delay: Optional[float] = None,
    min_gap: Optional[float] = None,
) -> Tuple[bool, float, float]:
    """
    Find the first safe slot at or after ``requested_start``.

    ``speech_intervals`` must already include safety padding (use
    ``_expand_speech_intervals``); ``scheduled_clips`` are existing
    placements to avoid. Returns ``(found, start, end)``.
    """
    if video_duration <= 0.0:
        return False, 0.0, 0.0

    delay = _max_delay_seconds() if max_delay is None else max(0.0, max_delay)
    gap = _min_gap_seconds() if min_gap is None else max(0.0, min_gap)

    # Guard against infinite loop when slot_duration <= min_gap
    if required_duration <= gap + 1e-9:
        return False, 0.0, 0.0

    occupied = _occupancy(speech_intervals, scheduled_clips)
    current = max(0.0, float(requested_start))
    search_limit = (
        video_duration
        if delay <= 0.0
        else min(video_duration, float(requested_start) + delay)
    )

    while current + required_duration <= video_duration + 1e-9:
        if current > search_limit + _EPSILON:
            break

        candidate_end = current + required_duration
        conflict: Optional[Tuple[float, float]] = None
        for occ_start, occ_end in occupied:
            if _too_close(current, candidate_end, occ_start, occ_end, gap):
                conflict = (occ_start, occ_end)
                break

        if conflict is None:
            final_end = min(candidate_end, video_duration)
            return True, round(current, 2), round(final_end, 2)

        # Jump past the conflicting interval with the minimum separation.
        occ_start, occ_end = conflict
        if occ_end <= current + _EPSILON and occ_start <= current:
            # Conflict came from a trailing traversal; advance minimally.
            current = current + max(gap, 0.05)
        else:
            current = occ_end + gap

    return False, 0.0, 0.0


def shorten_description(text: str, max_words: int) -> str:
    """
    Shorten narration text to at most ``max_words`` without ellipses.

    Truncation happens at the most natural boundary available (clause comma,
    then word boundary) and never leaves a dangling function word.
    """
    cleaned = _WHITESPACE_RE.sub(" ", text).strip()
    if max_words <= 0:
        return ""

    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned

    candidate = words[:max_words]
    # Prefer a clause boundary if one exists late in the window.
    joined = " ".join(candidate)
    if "," in joined:
        head = joined.rsplit(",", 1)[0].strip()
        if len(head.split()) >= max(3, max_words // 2):
            candidate = head.split()

    while candidate and candidate[-1].lower().strip(",.;:!?") in _TRAILING_STOPWORDS:
        candidate.pop()
    if not candidate:
        candidate = words[:max_words]

    shortened = " ".join(candidate).strip()
    shortened = shortened.rstrip(",.;:!? ")
    return shortened


def _shorten_variants(
    text: str,
    minimum_words: int = 3,
) -> List[str]:
    """Return progressively shorter variants of ``text`` (longest first)."""
    word_count = len(text.strip().split())
    if word_count <= minimum_words:
        return []

    variants: List[str] = []
    for fraction in (0.75, 0.5, 0.34):
        budget = max(minimum_words, int(word_count * fraction))
        if budget >= word_count:
            continue
        candidate = shorten_description(text, budget)
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def _make_clip(
    description: Dict[str, Any],
    text: str,
    start: float,
    end: float,
    duration: float,
    original_text: str,
) -> Dict[str, Any]:
    return {
        "description_id": str(description.get("id", "desc")),
        "text": text,
        "original_text": original_text,
        "priority": float(
            description.get("priority", description.get("importance", 0.5))
        ),
        "scheduled_start": start,
        "scheduled_end": end,
        "estimated_duration": round(duration, 2),
        "shortened": text != original_text,
        "status": "scheduled",
    }


def schedule_narration_clips(
    descriptions: Sequence[Dict[str, Any]],
    protected_speech_intervals: Sequence[Dict[str, float]],
    video_duration: float,
    min_gap: Optional[float] = None,
    max_delay: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Schedule narration clips into dialogue-safe gaps.

    Higher-priority descriptions are placed first so constrained schedules
    keep plot-relevant narration. When a clip does not fit, the scheduler
    attempts progressively shorter variants before omitting it.
    """
    if video_duration <= 0.0:
        raise SchedulingError("video_duration must be positive")

    gap = _min_gap_seconds() if min_gap is None else max(0.0, min_gap)
    delay = _max_delay_seconds() if max_delay is None else max(0.0, max_delay)
    expanded_speech = _expand_speech_intervals(protected_speech_intervals, video_duration)

    if settings.SCHEDULER_PRIORITY_SORTING:
        ordered = sorted(
            descriptions,
            key=lambda item: (
                -float(item.get("priority", item.get("importance", 0.5))),
                float(item.get("start", 0.0)),
            ),
        )
    else:
        ordered = sorted(descriptions, key=lambda item: float(item.get("start", 0.0)))

    logger.info(
        "Scheduling %d descriptions against %d protected speech intervals "
        "(padding=%.3fs, min_gap=%.3fs).",
        len(ordered),
        len(protected_speech_intervals),
        _padding_seconds(),
        gap,
    )

    scheduled: List[Dict[str, Any]] = []
    omitted: List[Dict[str, Any]] = []
    placed_clips: List[Dict[str, Any]] = []

    for description in ordered:
        desc_id = str(description.get("id", "desc"))
        text = str(description.get("text", "")).strip()
        original_text = text
        requested_start = float(description.get("start", 0.0))

        if not text:
            omitted.append(
                {
                    "description_id": desc_id,
                    "text": text,
                    "status": "omitted",
                    "reason": "Empty description text",
                }
            )
            continue

        if requested_start >= video_duration:
            omitted.append(
                {
                    "description_id": desc_id,
                    "text": text,
                    "status": "omitted",
                    "reason": "Requested start is beyond video duration",
                }
            )
            continue

        estimated_duration = estimate_speech_duration(text)
        found, start, end = find_available_gap(
            requested_start=requested_start,
            required_duration=estimated_duration,
            speech_intervals=expanded_speech,
            scheduled_clips=placed_clips,
            video_duration=video_duration,
            max_delay=delay,
            min_gap=gap,
        )

        if found:
            clip = _make_clip(
                description, text, start, end, estimated_duration, original_text
            )
            placed_clips.append(clip)
            scheduled.append(clip)
            continue

        if settings.SCHEDULER_AUTO_SHORTEN:
            for shortened_text in _shorten_variants(text):
                short_duration = estimate_speech_duration(shortened_text)
                found, start, end = find_available_gap(
                    requested_start=requested_start,
                    required_duration=short_duration,
                    speech_intervals=expanded_speech,
                    scheduled_clips=placed_clips,
                    video_duration=video_duration,
                    max_delay=delay,
                    min_gap=gap,
                )
                if found:
                    clip = _make_clip(
                        description,
                        shortened_text,
                        start,
                        end,
                        short_duration,
                        original_text,
                    )
                    placed_clips.append(clip)
                    scheduled.append(clip)
                    break
            else:
                omitted.append(
                    {
                        "description_id": desc_id,
                        "text": text,
                        "status": "omitted",
                        "reason": (
                            "No suitable narration gap without overlapping speech"
                        ),
                    }
                )
            continue

        omitted.append(
            {
                "description_id": desc_id,
                "text": text,
                "status": "omitted",
                "reason": "No suitable narration gap without overlapping speech",
            }
        )

    scheduled.sort(key=lambda clip: clip["scheduled_start"])
    logger.info(
        "Scheduling complete: %d scheduled, %d omitted.",
        len(scheduled),
        len(omitted),
    )
    return {
        "scheduled": scheduled,
        "omitted": omitted,
        "stats": {
            "scheduled": len(scheduled),
            "omitted": len(omitted),
            "shortened": sum(1 for clip in scheduled if clip.get("shortened")),
        },
    }


def _placement_is_safe(
    start: float,
    end: float,
    expanded_speech: Sequence[Dict[str, float]],
    placed_clips: Sequence[Dict[str, Any]],
    video_duration: float,
    min_gap: float,
) -> bool:
    if start < 0.0 or end > video_duration + _EPSILON or end <= start:
        return False
    for segment in expanded_speech:
        if _too_close(
            start,
            end,
            float(segment["start"]),
            float(segment["end"]),
            min_gap,
        ):
            return False
    for clip in placed_clips:
        if _too_close(
            start,
            end,
            float(clip["scheduled_start"]),
            float(clip["scheduled_end"]),
            min_gap,
        ):
            return False
    return True


def reschedule_with_actual_durations(
    clips: Sequence[Dict[str, Any]],
    protected_speech_intervals: Sequence[Dict[str, float]],
    video_duration: float,
    min_gap: Optional[float] = None,
    max_delay: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Re-verify a schedule using real TTS clip durations.

    Clips keep their slot when it is still safe. When actual audio grew past
    the original estimate, the clip is moved to the next safe gap; when no
    gap exists it is omitted. This is the post-TTS validation loop required
    by the dialogue-protection guarantees.
    """
    if video_duration <= 0.0:
        raise SchedulingError("video_duration must be positive")

    gap = _min_gap_seconds() if min_gap is None else max(0.0, min_gap)
    delay = _max_delay_seconds() if max_delay is None else max(0.0, max_delay)
    expanded_speech = _expand_speech_intervals(protected_speech_intervals, video_duration)

    ordered = sorted(
        clips,
        key=lambda item: (
            -float(item.get("priority", 0.5)),
            float(item.get("scheduled_start", item.get("start", 0.0))),
        ),
    )

    scheduled: List[Dict[str, Any]] = []
    omitted: List[Dict[str, Any]] = []
    placed: List[Dict[str, Any]] = []
    rescheduled_count = 0

    for clip in ordered:
        item = dict(clip)
        desc_id = str(item.get("description_id", item.get("id", "desc")))
        text = str(item.get("text", "")).strip()
        actual_duration = float(
            item.get(
                "actual_duration",
                item.get("duration", item.get("estimated_duration", 0.0)),
            )
        )
        if actual_duration <= 0.0:
            actual_duration = estimate_speech_duration(text)

        requested_start = float(
            item.get("scheduled_start", item.get("start", 0.0))
        )

        if _placement_is_safe(
            requested_start,
            requested_start + actual_duration,
            expanded_speech,
            placed,
            video_duration,
            gap,
        ):
            final_start = requested_start
        else:
            found, final_start, _ = find_available_gap(
                requested_start=requested_start,
                required_duration=actual_duration,
                speech_intervals=expanded_speech,
                scheduled_clips=placed,
                video_duration=video_duration,
                max_delay=delay,
                min_gap=gap,
            )
            if not found:
                omitted.append(
                    {
                        **item,
                        "description_id": desc_id,
                        "status": "omitted",
                        "reason": (
                            "Actual TTS duration no longer fits any safe gap"
                        ),
                    }
                )
                logger.warning(
                    "Omitting '%s' after TTS: actual duration %.2fs has no safe gap.",
                    desc_id,
                    actual_duration,
                )
                continue
            rescheduled_count += 1
            logger.info(
                "Rescheduled '%s' from %.2fs to %.2fs after TTS (actual %.2fs).",
                desc_id,
                requested_start,
                final_start,
                actual_duration,
            )

        item["scheduled_start"] = round(final_start, 2)
        item["scheduled_end"] = round(final_start + actual_duration, 2)
        item["duration"] = round(actual_duration, 2)
        item["status"] = "RESCHEDULED" if rescheduled_count and final_start != requested_start else "VALIDATED"
        placed.append(item)
        scheduled.append(item)

    scheduled.sort(key=lambda entry: entry["scheduled_start"])
    logger.info(
        "Post-TTS revalidation: %d scheduled, %d omitted, %d rescheduled.",
        len(scheduled),
        len(omitted),
        rescheduled_count,
    )
    return {
        "scheduled": scheduled,
        "omitted": omitted,
        "stats": {
            "scheduled": len(scheduled),
            "omitted": len(omitted),
            "rescheduled": rescheduled_count,
        },
    }


def validate_clip_placement(
    scheduled_start: float,
    actual_duration: float,
    speech_intervals: Sequence[Dict[str, float]],
    video_duration: float,
    min_gap: Optional[float] = None,
) -> Tuple[bool, float, float]:
    """Validate a single clip against padded speech and video bounds."""
    scheduled_end = round(scheduled_start + actual_duration, 2)
    if scheduled_start < 0.0 or scheduled_end > video_duration + _EPSILON:
        return False, scheduled_start, scheduled_end

    gap = _min_gap_seconds() if min_gap is None else max(0.0, min_gap)
    expanded = _expand_speech_intervals(speech_intervals, video_duration)
    for segment in expanded:
        if _too_close(
            scheduled_start,
            scheduled_end,
            float(segment["start"]),
            float(segment["end"]),
            gap,
        ):
            return False, scheduled_start, scheduled_end

    return True, scheduled_start, scheduled_end


def verify_schedule_no_overlap(
    clips: Sequence[Dict[str, Any]],
    protected_speech_intervals: Sequence[Dict[str, float]],
    video_duration: Optional[float] = None,
) -> bool:
    """Final guard: confirm narration never overlaps protected speech."""
    expanded = _expand_speech_intervals(protected_speech_intervals, video_duration)
    for clip in clips:
        start = float(clip.get("scheduled_start", 0.0))
        end = float(clip.get("scheduled_end", 0.0))
        for segment in expanded:
            if intervals_overlap(start, end, segment["start"], segment["end"]):
                logger.error(
                    "Narration overlap detected: clip [%.2f-%.2f] vs speech [%.2f-%.2f].",
                    start,
                    end,
                    segment["start"],
                    segment["end"],
                )
                return False
    return True