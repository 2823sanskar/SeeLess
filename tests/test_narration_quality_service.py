"""
tests/test_narration_quality_service.py
---------------------------------------
Unit tests for Phase 3 narration quality checks.
"""

from app.services.narration_quality_service import NarrationQualityService


class TestNormalization:
    def setup_method(self):
        self.service = NarrationQualityService()

    def test_capitalizes_and_adds_terminal_punctuation(self):
        assert self.service.normalize_text("a man runs") == "A man runs."

    def test_rewrites_wordy_phrasing(self):
        assert (
            self.service.normalize_text("in order to open the door")
            == "To open the door."
        )

    def test_collapses_whitespace_and_ellipsis(self):
        assert self.service.normalize_text("A  man...  waits") == "A man. waits."

    def test_empty_text_returns_empty(self):
        assert self.service.normalize_text("   ") == ""


class TestQualityChecks:
    def setup_method(self):
        self.service = NarrationQualityService(max_words=12, min_words=3)

    def test_rejects_speculative_language(self):
        valid, rejected = self.service.validate_descriptions(
            [{"id": "d1", "text": "The man probably leaves."}]
        )
        assert valid == []
        assert "speculative_language" in rejected[0]["rejection_reasons"]

    def test_rejects_too_short_text(self):
        valid, rejected = self.service.validate_descriptions(
            [{"id": "d1", "text": "He runs."}]
        )
        assert valid == []
        assert any("too_short" in reason for reason in rejected[0]["rejection_reasons"])

    def test_accepts_grounded_description(self):
        valid, rejected = self.service.validate_descriptions(
            [{"id": "d1", "text": "The woman opens the door."}]
        )
        assert len(valid) == 1
        assert rejected == []
        assert valid[0]["text"] == "The woman opens the door."

    def test_deduplicates_descriptions(self):
        descriptions = [
            {"id": "a", "start": 1.0, "text": "John runs."},
            {"id": "b", "start": 1.2, "text": "John runs."},
        ]
        kept = self.service.deduplicate(descriptions)
        assert [item["id"] for item in kept] == ["a"]

    def test_shorten_respects_max_words(self):
        text = (
            "The tall man in the blue jacket walks slowly across the crowded room "
            "while carrying a large wooden box."
        )
        shortened = self.service.shorten(text, max_words=8)
        assert len(shortened.split()) <= 8
        assert "..." not in shortened
        assert shortened.endswith(".")

    def test_process_repairs_overlong_and_rejects_speculation(self):
        descriptions = [
            {
                "id": "long",
                "start": 1.0,
                "text": (
                    "The tall man in the blue jacket walks slowly across the "
                    "crowded room while carrying a large wooden box."
                ),
            },
            {"id": "hedged", "start": 2.0, "text": "The man might be leaving."},
            {"id": "safe", "start": 3.0, "text": "The woman opens the door."},
        ]
        valid, rejected = self.service.process_descriptions(descriptions)

        valid_ids = {item["id"] for item in valid}
        rejected_ids = {item["id"] for item in rejected}
        assert valid_ids == {"long", "safe"}
        assert rejected_ids == {"hedged"}
        long_item = next(item for item in valid if item["id"] == "long")
        assert len(long_item["text"].split()) <= self.service.max_words


class TestScoring:
    def setup_method(self):
        self.service = NarrationQualityService()

    def test_conciseness_score_prefers_ideal_range(self):
        assert self.service.conciseness_score("The man opens the door.") == 1.0
        assert self.service.conciseness_score("He runs.") < 1.0

    def test_ground_check_uses_token_overlap(self):
        assert self.service.ground_check(
            "The woman opens the door.", ["a woman opens a door"]
        )
        assert not self.service.ground_check(
            "The woman opens the door.", ["a car explodes"]
        )
