import os
import pytest
from app.services.scheduler_service import (
    estimate_speech_duration,
    find_available_gap,
    schedule_narration_clips,
    validate_clip_placement
)

def test_estimate_speech_duration():
    text = "A man enters the room."
    dur = estimate_speech_duration(text)
    assert dur > 1.0
    assert dur < 5.0

def test_schedule_in_safe_gap():
    # Gap between 0.0 and 5.0, speech at 5.0-8.0
    descriptions = [
        {"id": "d1", "start": 1.0, "end": 3.0, "text": "A man enters.", "priority": 0.9}
    ]
    speech = [{"start": 5.0, "end": 8.0}]
    res = schedule_narration_clips(descriptions, speech, video_duration=20.0)
    
    assert len(res["scheduled"]) == 1
    assert res["scheduled"][0]["scheduled_start"] >= 1.0
    assert res["scheduled"][0]["scheduled_end"] <= 5.0

def test_schedule_shifted_after_dialogue():
    # Visual event at 5.5, but dialogue runs from 5.0 to 8.0
    descriptions = [
        {"id": "d2", "start": 5.5, "end": 7.0, "text": "He looks away anxiously.", "priority": 0.9}
    ]
    speech = [{"start": 5.0, "end": 8.0}]
    res = schedule_narration_clips(descriptions, speech, video_duration=20.0)

    assert len(res["scheduled"]) == 1
    # Must be placed at or after 8.0 (when dialogue finishes)
    assert res["scheduled"][0]["scheduled_start"] >= 8.0

def test_schedule_rejected_when_no_gap():
    # Wall-to-wall speech
    descriptions = [
        {"id": "d3", "start": 1.0, "end": 2.0, "text": "Extensive visual detail.", "priority": 0.5}
    ]
    speech = [{"start": 0.0, "end": 20.0}]
    res = schedule_narration_clips(descriptions, speech, video_duration=20.0)

    assert len(res["scheduled"]) == 0
    assert len(res["omitted"]) == 1
    assert res["omitted"][0]["status"] == "omitted"

def test_no_dialogue_overlap():
    descriptions = [
        {"id": "d1", "start": 2.0, "end": 4.0, "text": "Character opens door.", "priority": 0.9},
        {"id": "d2", "start": 10.0, "end": 12.0, "text": "Character sits on couch.", "priority": 0.8}
    ]
    speech = [
        {"start": 3.0, "end": 7.0},
        {"start": 11.0, "end": 14.0}
    ]
    res = schedule_narration_clips(descriptions, speech, video_duration=25.0)
    
    for clip in res["scheduled"]:
        for sp in speech:
            # Overlap condition: max(s1, s2) < min(e1, e2)
            has_overlap = max(clip["scheduled_start"], sp["start"]) < min(clip["scheduled_end"], sp["end"])
            assert not has_overlap, f"Clip {clip['description_id']} overlapped with speech interval {sp}"

