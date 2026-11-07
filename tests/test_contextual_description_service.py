"""
tests/test_contextual_description_service.py
--------------------------------------------
Unit tests for Phase 3 contextual description generation.
"""

from app.services.context_service import ContextService
from app.services.contextual_description_service import (
    ContextualDescriptionService,
    _definite_form,
    _subject_key,
)


class TestHelpers:
    def test_subject_key_strips_article_and_case(self):
        assert _subject_key("A Man") == "man"
        assert _subject_key("the woman") == "woman"

    def test_definite_form(self):
        assert _definite_form("A man") == "The man"
        assert _definite_form("The woman") == "The woman"


class TestGenerateDescriptions:
    def setup_method(self):
        self.service = ContextualDescriptionService()

    def test_formats_natural_sentence(self):
        descriptions = self.service.generate_descriptions(
            [
                {
                    "start": 1.0,
                    "end": 2.5,
                    "subject": "a woman",
                    "action": "walks quickly to the window",
                    "importance": 0.8,
                }
            ]
        )
        assert len(descriptions) == 1
        text = descriptions[0]["text"]
        assert text[0].isupper()
        assert text.endswith(".")
        assert "walks quickly to the window" in text

    def test_tracks_character_across_mentions(self):
        descriptions = self.service.generate_descriptions(
            [
                {"start": 1.0, "end": 2.0, "subject": "A man", "action": "enters"},
                {"start": 5.0, "end": 6.0, "subject": "A man", "action": "opens the door"},
            ]
        )
        assert descriptions[0]["text"].startswith("A man")
        assert descriptions[1]["text"].startswith("The man")

    def test_uses_scene_location_for_entry(self):
        self.service.record_scene(1, "kitchen", [])
        descriptions = self.service.generate_descriptions(
            [
                {
                    "start": 2.0,
                    "end": 3.0,
                    "scene_number": 1,
                    "subject": "A boy",
                    "action": "enters",
                }
            ]
        )
        assert descriptions[0]["text"] == "A boy enters the kitchen."

    def test_adds_grounded_expression(self):
        descriptions = self.service.generate_descriptions(
            [
                {
                    "start": 1.0,
                    "end": 2.0,
                    "subject": "A girl",
                    "action": "looks up",
                    "expressions": [{"expression": "smiling", "confidence": 0.8}],
                }
            ]
        )
        assert descriptions[0]["text"] == "A girl looks up, smiling."

    def test_ignores_vague_expression_labels(self):
        descriptions = self.service.generate_descriptions(
            [
                {
                    "start": 1.0,
                    "end": 2.0,
                    "subject": "A girl",
                    "action": "looks up",
                    "expressions": [{"expression": "expressive"}],
                }
            ]
        )
        assert descriptions[0]["text"] == "A girl looks up."

    def test_limits_word_count(self):
        service = ContextualDescriptionService(max_words=6)
        descriptions = service.generate_descriptions(
            [
                {
                    "start": 1.0,
                    "end": 2.0,
                    "subject": "A tall man in a blue jacket",
                    "action": "walks slowly across the crowded room",
                }
            ]
        )
        assert len(descriptions[0]["text"].split()) <= 6

    def test_empty_events_returns_empty(self):
        assert self.service.generate_descriptions([]) == []


class TestEnrichWithContext:
    def test_attaches_character_context(self):
        context = ContextService()
        context.update_character(
            "John", {"label": "John", "last_seen_scene": 3}
        )
        service = ContextualDescriptionService(context_service=context)

        enriched = service.enrich_with_context(
            [{"id": "d1", "start": 1.0, "end": 2.0, "text": "John runs."}]
        )
        assert "Known characters: John" in enriched[0]["context"]

    def test_attaches_matching_event_location(self):
        service = ContextualDescriptionService()
        service.record_scene(2, "balcony", [])
        enriched = service.enrich_with_context(
            [{"id": "d1", "start": 9.0, "end": 10.0, "text": "A man waits."}],
            visual_events=[
                {"start": 9.1, "scene_number": 2, "subject": "A man", "action": "waits"}
            ],
        )
        assert enriched[0]["location"] == "balcony"

    def test_returns_copies_without_mutating_input(self):
        service = ContextualDescriptionService()
        original = {"id": "d1", "start": 1.0, "end": 2.0, "text": "A man runs."}
        enriched = service.enrich_with_context([original])
        enriched[0]["text"] = "changed"
        assert original["text"] == "A man runs."
