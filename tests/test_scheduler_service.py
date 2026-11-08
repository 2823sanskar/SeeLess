import pytest
from app.services.scheduler_service import reschedule_with_actual_durations


def test_reschedule_status_flag():
    # Test that when clips are rescheduled, only the ones that actually shift get "RESCHEDULED",
    # while the ones that remain in place get "VALIDATED".
    # Previously, because of the running counter `rescheduled_count` being used globally:
    # - If clip 0 stayed in place (not rescheduled), rescheduled_count == 0, so clip 1 (which shifted) got "VALIDATED" instead of "RESCHEDULED" because `rescheduled_count and final_start != requested_start` evaluated to False (since rescheduled_count was 0).
    # - Or if clip 0 shifted (rescheduled_count = 1), then if clip 1 stayed in place (final_start == requested_start), it incorrectly got "RESCHEDULED" because `rescheduled_count` was non-zero!

    clips = [
        {
            "description_id": "clip_1",
            "text": "First clip",
            "scheduled_start": 2.0,
            "scheduled_end": 4.0,
            "actual_duration": 3.0,  # stays at 2.0, ends at 5.0 (safe: gap of 0.3 >= min_gap 0.2)
        },
        {
            "description_id": "clip_2",
            "text": "Second clip",
            "scheduled_start": 6.0,
            "scheduled_end": 8.0,
            "actual_duration": 4.0,  # conflicts with speech at [5.5, 10.0], so must be shifted!
        },
    ]

    protected_speech_intervals = [
        {"start": 5.5, "end": 10.0}
    ]

    video_duration = 30.0

    result = reschedule_with_actual_durations(
        clips=clips,
        protected_speech_intervals=protected_speech_intervals,
        video_duration=video_duration,
        min_gap=0.2,  # Use 0.2 so clip_1 has gap >= min_gap but clip_2 still conflicts
        max_delay=20.0,
    )

    scheduled = result["scheduled"]
    assert len(scheduled) == 2

    # Clip 1 should stay at 2.0 and have status "VALIDATED"
    assert scheduled[0]["description_id"] == "clip_1"
    assert scheduled[0]["scheduled_start"] == 2.0
    assert scheduled[0]["status"] == "VALIDATED"

    # Clip 2 should be shifted past speech end and have status "RESCHEDULED"
    assert scheduled[1]["description_id"] == "clip_2"
    assert scheduled[1]["scheduled_start"] == 10.6
    assert scheduled[1]["status"] == "RESCHEDULED"


def test_reschedule_first_clip_validated_second():
    # Test the case where first clip is rescheduled, but second clip stays in place.
    # Previously: rescheduled_count was 1 from clip 0, so clip 1 incorrectly got "RESCHEDULED"
    # even though it didn't move.

    clips = [
        {
            "description_id": "clip_1",
            "text": "First clip",
            "scheduled_start": 5.8,
            "scheduled_end": 7.8,
            "actual_duration": 3.0,  # Conflicts with speech [5.5, 10.0] -> must move
        },
        {
            "description_id": "clip_2",
            "text": "Second clip",
            "scheduled_start": 15.0,
            "scheduled_end": 17.0,
            "actual_duration": 2.0,  # Stays at 15.0, ends at 17.0 (safe)
        },
    ]

    protected_speech_intervals = [
        {"start": 5.5, "end": 10.0}
    ]

    video_duration = 30.0

    result = reschedule_with_actual_durations(
        clips=clips,
        protected_speech_intervals=protected_speech_intervals,
        video_duration=video_duration,
        min_gap=0.2,
        max_delay=20.0,
    )

    scheduled = result["scheduled"]
    assert len(scheduled) == 2

    # Clip 1 should be rescheduled to after speech (10.2 + 0.2 = 10.4)
    assert scheduled[0]["description_id"] == "clip_1"
    assert scheduled[0]["status"] == "RESCHEDULED"
    # Clip 2 should stay at 15.0 and be "VALIDATED" (not RESCHEDULED!)
    assert scheduled[1]["description_id"] == "clip_2"
    assert scheduled[1]["scheduled_start"] == 15.0
    assert scheduled[1]["status"] == "VALIDATED"
