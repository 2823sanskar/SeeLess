"""
tests/test_character_service.py
-------------------------------
Unit tests for character tracking service.
"""

import pytest

from app.services.character_service import CharacterService


class TestCharacterService:
    """Tests for character detection and tracking."""

    def setup_method(self):
        self.service = CharacterService()

    def test_detect_from_events_extracts_subjects(self):
        events = [
            {"subject": "John", "start": 1.0, "end": 3.0, "confidence": 0.9},
            {"subject": "Mary", "start": 2.0, "end": 4.0, "confidence": 0.8},
            {"subject": "The scene", "start": 0.0, "end": 5.0, "confidence": 0.5},  # should be filtered
        ]
        detected = self.service.detect_from_events(events)
        assert len(detected) == 2
        labels = {d["label"] for d in detected}
        assert labels == {"John", "Mary"}

    def test_detect_from_events_filters_low_confidence(self):
        events = [
            {"subject": "John", "confidence": 0.9},
            {"subject": "Mary", "confidence": 0.3},  # below threshold
        ]
        detected = self.service.detect_from_events(events)
        assert len(detected) == 1
        assert detected[0]["label"] == "John"

    def test_detect_from_events_updates_character_state(self):
        events = [
            {"subject": "John", "start": 1.0, "end": 3.0, "confidence": 0.9},
        ]
        self.service.detect_from_events(events)
        char = self.service.get_character_summary()
        assert len(char) == 1
        assert char[0]["label"] == "John"
        assert char[0]["first_seen"] == 1.0
        assert char[0]["last_seen"] == 3.0
        assert char[0]["appearances"] == 1

    def test_match_or_create_returns_existing(self):
        events = [
            {"subject": "John", "start": 1.0, "end": 3.0, "confidence": 0.9},
        ]
        self.service.detect_from_events(events)
        events2 = [
            {"subject": "John", "start": 4.0, "end": 6.0, "confidence": 0.8},
        ]
        detected2 = self.service.detect_from_events(events2)
        assert len(detected2) == 1
        assert detected2[0]["character_id"] == detected2[0]["character_id"]
        # Second detection should have same ID
        summary = self.service.get_character_summary()
        assert summary[0]["appearances"] == 2
        assert summary[0]["last_seen"] == 6.0

    def test_track_across_scenes(self):
        scene1 = [
            {"subject": "John", "start": 1.0, "end": 3.0, "confidence": 0.9},
            {"subject": "Mary", "start": 2.0, "end": 4.0, "confidence": 0.8},
        ]
        scene2 = [
            {"subject": "John", "start": 10.0, "end": 12.0, "confidence": 0.9},
        ]
        result = self.service.track_across_scenes([scene1, scene2])
        assert len(result) == 2
        john = next(c for c in result.values() if c["label"] == "John")
        assert john["scenes"] == [0, 1]
        assert john["appearances"] == 2
        mary = next(c for c in result.values() if c["label"] == "Mary")
        assert mary["scenes"] == [0]
        assert mary["appearances"] == 1

    def test_get_character_by_id(self):
        events = [{"subject": "John", "start": 1.0, "end": 3.0, "confidence": 0.9}]
        self.service.detect_from_events(events)
        char_id = self.service.get_character_summary()[0]["character_id"]
        found = self.service.get_character_by_id(char_id)
        assert found is not None
        assert found["label"] == "John"
        assert self.service.get_character_by_id("nonexistent") is None