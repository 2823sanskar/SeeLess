"""
tests/test_prioritization_service.py
------------------------------------
Unit tests for Phase 3 event prioritization.
"""

import pytest

from app.services.prioritization_service import (
    PrioritizationError,
    demote_low_priority,
    filter_speculative,
    is_speculative,
    prioritize_events,
    rank_by_importance,
    score_event,
)


class TestScoreEvent:
    def test_score_is_within_unit_range(self):
        score = score_event(
            {"subject": "A man", "action": "runs", "importance": 1.5}
        )
        assert 0.0 <= score <= 1.0

    def test_high_importance_action_boosted(self):
        routine = score_event(
            {"subject": "A man", "action": "blinks", "importance": 0.4}
        )
        critical = score_event(
            {"subject": "A man", "action": "draws a weapon", "importance": 0.4}
        )
        assert critical > routine

    def test_invalid_importance_falls_back(self):
        score = score_event({"subject": "A man", "action": "runs", "importance": "high"})
        assert 0.0 <= score <= 1.0


class TestPrioritizeEvents:
    def test_plot_relevant_event_ranks_first(self):
        events = [
            {
                "id": "routine",
                "start": 10.0,
                "subject": "A man",
                "action": "blinks",
                "importance": 0.6,
                "confidence": 0.9,
            },
            {
                "id": "critical",
                "start": 20.0,
                "subject": "A woman",
                "action": "draws a weapon",
                "importance": 0.6,
                "confidence": 0.9,
            },
        ]
        ranked = prioritize_events(events)
        assert ranked[0]["id"] == "critical"
        assert "importance_score" in ranked[0]
        assert "priority" in ranked[0]

    def test_duplicate_descriptions_removed(self):
        events = [
            {"id": "a", "start": 1.0, "subject": "John", "action": "runs"},
            {"id": "b", "start": 1.2, "subject": "John", "action": "runs"},
        ]
        ranked = prioritize_events(events)
        assert len(ranked) == 1

    def test_max_descriptions_cap_applied(self):
        events = [
            {"id": str(i), "start": float(i), "subject": f"Person {i}", "action": "walks"}
            for i in range(8)
        ]
        ranked = prioritize_events(events, max_descriptions=3)
        assert len(ranked) == 3

    def test_speculative_events_filtered(self):
        events = [
            {
                "id": "safe",
                "start": 1.0,
                "subject": "A man",
                "action": "opens the door",
            },
            {
                "id": "speculative",
                "start": 2.0,
                "subject": "A man",
                "action": "probably runs away",
            },
        ]
        ranked = prioritize_events(events)
        ids = {event["id"] for event in ranked}
        assert ids == {"safe"}

    def test_empty_input_returns_empty(self):
        assert prioritize_events([]) == []


class TestSpeculationHelpers:
    def test_is_speculative_detects_hedges(self):
        assert is_speculative("The man seems to be leaving.")
        assert not is_speculative("The man leaves the room.")

    def test_filter_speculative_keeps_grounded(self):
        items = [
            {"id": "1", "text": "The car explodes."},
            {"id": "2", "text": "The car might be red."},
        ]
        kept = filter_speculative(items)
        assert [item["id"] for item in kept] == ["1"]


class TestDemotionAndRanking:
    def test_demote_low_priority_keeps_best(self):
        descriptions = [
            {"id": "low", "start": 1.0, "priority": 0.2},
            {"id": "high", "start": 2.0, "priority": 0.9},
            {"id": "mid", "start": 3.0, "priority": 0.5},
        ]
        kept, dropped = demote_low_priority(descriptions, available_slots=2)
        assert [item["id"] for item in kept] == ["high", "mid"]
        assert [item["id"] for item in dropped] == ["low"]

    def test_demote_negative_slots_raises(self):
        with pytest.raises(PrioritizationError):
            demote_low_priority([], available_slots=-1)

    def test_rank_by_importance(self):
        descriptions = [
            {"id": "a", "priority": 0.1, "start": 1.0},
            {"id": "b", "priority": 0.8, "start": 5.0},
        ]
        ranked = rank_by_importance(descriptions)
        assert ranked[0]["id"] == "b"
