"""
tests/test_dialogue_protection_service.py
-----------------------------------------
Unit tests for Phase 3 strict dialogue protection.
"""

import pytest

from app.services.dialogue_protection_service import (
    DialogueProtectionError,
    DialogueProtectionService,
)


class TestDialogueProtectionService:
    def setup_method(self):
        self.service = DialogueProtectionService(
            safety_padding_ms=200.0,
            max_reschedule_attempts=3,
            min_gap_seconds=0.3,
        )

    def test_check_overlap_includes_safety_padding(self):
        speech = [{"start": 5.0, "end": 6.0}]
        has_overlap, conflict = self.service.check_overlap(4.9, 5.1, speech)
        assert has_overlap
        assert conflict == (4.8, 6.2)

        has_overlap, _ = self.service.check_overlap(4.0, 4.6, speech)
        assert not has_overlap

    def test_validate_clip_rejects_video_overflow(self):
        valid, _, end = self.service.validate_clip(
            scheduled_start=9.5,
            actual_duration=2.0,
            speech_intervals=[],
            video_duration=10.0,
        )
        assert not valid
        assert end > 10.0

    def test_validate_clip_rejects_speech_overlap(self):
        valid, _, _ = self.service.validate_clip(
            scheduled_start=4.9,
            actual_duration=1.0,
            speech_intervals=[{"start": 5.0, "end": 6.0}],
            video_duration=20.0,
        )
        assert not valid

    def test_validate_clip_accepts_safe_placement(self):
        valid, start, end = self.service.validate_clip(
            scheduled_start=1.0,
            actual_duration=1.0,
            speech_intervals=[{"start": 5.0, "end": 6.0}],
            video_duration=20.0,
        )
        assert valid
        assert (start, end) == (1.0, 2.0)

    def test_validate_clip_requires_positive_duration(self):
        with pytest.raises(DialogueProtectionError):
            self.service.validate_clip(0.0, 0.0, [], 10.0)

    def test_reschedule_clip_avoids_padded_speech(self):
        found, start, end = self.service.reschedule_clip(
            requested_start=1.0,
            required_duration=2.0,
            speech_intervals=[{"start": 2.0, "end": 4.0}],
            scheduled_clips=[],
            video_duration=20.0,
            max_delay=15.0,
        )
        assert found
        assert start >= 4.2
        assert end <= 20.0

    def test_validate_all_clips_splits_valid_and_invalid(self):
        clips = [
            {"description_id": "safe", "scheduled_start": 1.0, "duration": 1.0},
            {"description_id": "unsafe", "scheduled_start": 5.5, "duration": 1.0},
        ]
        valid, invalid = self.service.validate_all_clips(
            clips, [{"start": 5.0, "end": 6.0}], video_duration=20.0
        )
        assert [clip["description_id"] for clip in valid] == ["safe"]
        assert [clip["description_id"] for clip in invalid] == ["unsafe"]
        assert invalid[0]["status"] == "INVALID"

    def test_revalidate_and_reschedule_uses_actual_durations(self):
        clips = [
            {
                "description_id": "d1",
                "text": "A man enters the room.",
                "priority": 0.9,
                "scheduled_start": 1.0,
                "estimated_duration": 1.0,
                "actual_duration": 5.0,
                "duration": 5.0,
            }
        ]
        result = self.service.revalidate_and_reschedule(
            clips, [{"start": 2.0, "end": 6.0}], video_duration=20.0
        )
        assert len(result["scheduled"]) == 1
        assert result["scheduled"][0]["scheduled_start"] >= 6.2
        assert self.service.verify_zero_overlap(
            result["scheduled"], [{"start": 2.0, "end": 6.0}]
        )

    def test_verify_zero_overlap_detects_conflict(self):
        clips = [{"scheduled_start": 5.0, "scheduled_end": 5.5}]
        speech = [{"start": 5.0, "end": 6.0}]
        assert not self.service.verify_zero_overlap(clips, speech)

    def test_verify_video_bounds(self):
        assert self.service.verify_video_bounds(
            [{"scheduled_start": 1.0, "scheduled_end": 2.0}], 10.0
        )
        assert not self.service.verify_video_bounds(
            [{"scheduled_start": 9.5, "scheduled_end": 10.5}], 10.0
        )
