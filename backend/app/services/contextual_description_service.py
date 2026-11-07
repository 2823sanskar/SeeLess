"""
contextual_description_service.py
----------------------------------
Context-aware description generation for the SeeLess narration engine.

Turns structured visual events into natural, flowing narration sentences
while preserving character continuity (first mention vs. return), location
history, and scene-to-scene context. Descriptions remain strictly grounded
in observed visual evidence: no dialogue paraphrasing and no speculation.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.config import settings
from app.utils.logging_utils import logger


class ContextualDescriptionError(Exception):
    """Raised when contextual description input is malformed."""


_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[.!?,;:\s]+$")
_LEADING_ARTICLE_RE = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)

# Concrete expressions only. Vague detector labels are intentionally ignored
# so we never assert an emotion that was not clearly observed.
_CONCRETE_EXPRESSIONS: Dict[str, str] = {
    "smiling": "smiling",
    "smile": "smiling",
    "laughing": "laughing",
    "frowning": "frowning",
    "crying": "crying",
    "surprised": "looking surprised",
    "shocked": "looking shocked",
    "angry": "looking angry",
    "scared": "looking frightened",
    "frightened": "looking frightened",
}

_ENTRY_VERBS: Tuple[str, ...] = (
    "enters", "entering", "walks into", "steps into", "comes into",
    "runs into", "moves into",
)
_ARRIVAL_VERBS: Tuple[str, ...] = ("arrives", "arriving", "arrives at")

_TRAILING_STOPWORDS: frozenset[str] = frozenset(
    {
        "and", "but", "or", "with", "to", "of", "in", "on", "at", "for",
        "the", "a", "an", "his", "her", "their", "as", "while", "then",
    }
)


def _clean_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _capitalize(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _strip_trailing_punctuation(text: str) -> str:
    return _TRAILING_PUNCT_RE.sub("", text).strip()


def _ensure_sentence(text: str) -> str:
    cleaned = _strip_trailing_punctuation(_clean_text(text))
    if not cleaned:
        return ""
    return _capitalize(cleaned) + "."


def _subject_key(subject: str) -> str:
    """Normalize a subject for continuity tracking (drop article/case)."""
    lowered = subject.strip().lower()
    lowered = _LEADING_ARTICLE_RE.sub("", lowered)
    return _clean_text(lowered)


def _definite_form(subject: str) -> str:
    """Convert an indefinite mention ("A man") to a definite one ("The man")."""
    cleaned = _clean_text(subject)
    match = _LEADING_ARTICLE_RE.match(cleaned)
    if match:
        return "The " + cleaned[match.end():]
    return "The " + cleaned


def _vague_subject(subject: str) -> bool:
    return _subject_key(subject) in {
        "scene", "camera", "view", "background", "figure", "person",
        "character", "someone", "something", "",
    }


def _trim_to_words(text: str, max_words: int) -> str:
    """Trim a sentence to ``max_words`` at the most natural boundary."""
    words = text.split()
    if len(words) <= max_words:
        return text

    candidate = words[:max_words]
    while candidate and candidate[-1].lower().strip(",.;:") in _TRAILING_STOPWORDS:
        candidate.pop()
    if not candidate:
        candidate = words[:max_words]

    trimmed = " ".join(candidate)
    if "," in trimmed:
        head = trimmed.rsplit(",", 1)[0].strip()
        if len(head.split()) >= max(3, max_words // 2):
            trimmed = head
    return trimmed


class ContextualDescriptionService:
    """
    Builds descriptions that maintain character and scene continuity.

    The service accepts either a ``ContextService`` (dict-based character
    context) or a ``CharacterService`` (list-based summary). It records
    scene history so later descriptions can refer back to established
    characters and locations.
    """

    def __init__(
        self,
        context_service: Optional[Any] = None,
        max_words: Optional[int] = None,
    ) -> None:
        self._context_service = context_service
        self._scene_history: List[Dict[str, Any]] = []
        self._scene_locations: Dict[int, str] = {}
        self._last_location: Optional[str] = None
        self._introduced_subjects: set[str] = set()
        self.max_words = int(max_words or settings.NARRATION_MAX_WORDS)

    # ------------------------------------------------------------------
    # Context plumbing
    # ------------------------------------------------------------------

    def set_context_service(self, context_service: Any) -> None:
        self._context_service = context_service

    def record_scene(
        self,
        scene_number: int,
        location: Optional[str],
        events: Sequence[Dict[str, Any]],
    ) -> None:
        """Record a processed scene for continuity context."""
        characters: List[str] = []
        for event in events:
            subject = str(event.get("subject") or "").strip()
            if subject and not _vague_subject(subject):
                characters.append(subject)

        self._scene_history.append(
            {
                "scene_number": int(scene_number),
                "location": location,
                "characters": characters,
                "start": events[0].get("start") if events else None,
                "end": events[-1].get("end") if events else None,
            }
        )
        if location:
            self._last_location = location
            self._scene_locations[int(scene_number)] = location

    def record_scenes(
        self,
        scenes: Sequence[Dict[str, Any]],
        events: Sequence[Dict[str, Any]],
    ) -> None:
        """Group events by ``scene_number`` and record each scene in order."""
        for scene in sorted(scenes, key=lambda item: item.get("scene_number", 0)):
            number = int(scene.get("scene_number", len(self._scene_history) + 1))
            scene_events = [
                event
                for event in events
                if int(event.get("scene_number", number)) == number
            ]
            self.record_scene(number, scene.get("location"), scene_events)

    def _character_map(self) -> Dict[str, Dict[str, Any]]:
        """Normalize whatever context provider was supplied into a map."""
        if self._context_service is None:
            return {}

        getter = getattr(self._context_service, "get_character_summary", None)
        if callable(getter):
            summary = getter() or []
            if isinstance(summary, dict):
                return {str(k): dict(v) for k, v in summary.items() if isinstance(v, dict)}
            return {
                str(item.get("label") or item.get("character_id") or idx): dict(item)
                for idx, item in enumerate(summary)
                if isinstance(item, dict)
            }

        getter = getattr(self._context_service, "get_character_continuity", None)
        if callable(getter):
            summary = getter() or {}
            if isinstance(summary, dict):
                return {str(k): dict(v) for k, v in summary.items() if isinstance(v, dict)}

        getter = getattr(self._context_service, "get_context_summary", None)
        if callable(getter):
            summary = getter() or {}
            characters = summary.get("characters") if isinstance(summary, dict) else None
            if isinstance(characters, dict):
                return {
                    str(k): dict(v) if isinstance(v, dict) else {"label": str(v)}
                    for k, v in characters.items()
                }
            if isinstance(characters, list):
                return {
                    str(item.get("label") or idx): dict(item)
                    for idx, item in enumerate(characters)
                    if isinstance(item, dict)
                }

        return {}

    def _get_previous_context(self) -> Dict[str, Any]:
        """Build a continuity summary from earlier scenes and characters."""
        context: Dict[str, Any] = {}

        characters = self._character_map()
        if characters:
            context["characters"] = characters

        if self._scene_history:
            previous = self._scene_history[-1]
            context["previous_scene"] = {
                "scene_number": previous["scene_number"],
                "location": previous.get("location"),
            }

        if self._last_location:
            context["current_location"] = self._last_location

        return context

    def _build_context_string(self, context: Dict[str, Any]) -> str:
        """Render context as a short natural-language block for prompts."""
        parts: List[str] = []

        if context.get("current_location"):
            parts.append(f"Current location: {context['current_location']}")

        previous = context.get("previous_scene")
        if previous and previous.get("location"):
            parts.append(f"Previous scene location: {previous['location']}")

        characters = context.get("characters") or {}
        labels: List[str] = []
        for character_id, info in characters.items():
            label = str(info.get("label") or character_id)
            last_scene = info.get("last_seen_scene")
            if last_scene is not None:
                labels.append(f"{label} (last seen scene {last_scene})")
            else:
                labels.append(label)
        if labels:
            parts.append(f"Known characters: {', '.join(labels)}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Sentence composition
    # ------------------------------------------------------------------

    def _subject_phrase(self, event: Dict[str, Any]) -> str:
        subject = _clean_text(str(event.get("subject") or ""))
        if not subject or _vague_subject(subject):
            subject = "The figure"

        key = _subject_key(subject)
        if key in self._introduced_subjects:
            phrase = _definite_form(subject)
        else:
            phrase = _capitalize(subject)
            self._introduced_subjects.add(key)
        return phrase

    def _action_phrase(self, event: Dict[str, Any], subject_phrase: str) -> str:
        action = _clean_text(str(event.get("action") or ""))
        action = action.replace("_", " ").strip()
        action = _strip_trailing_punctuation(action)
        if not action:
            action = "is visible on screen"

        lowered_action = action.lower()
        lowered_subject = subject_phrase.lower()
        if lowered_action.startswith(lowered_subject):
            # The action already carries the subject; avoid duplication.
            return _capitalize(action)

        return action

    def _location_phrase(self, event: Dict[str, Any], action: str) -> str:
        location = str(event.get("location") or "").strip()
        if not location:
            try:
                scene_number = int(event.get("scene_number", -1))
            except (TypeError, ValueError):
                scene_number = -1
            location = self._scene_locations.get(scene_number, "")

        if not location:
            return ""
        location = _strip_trailing_punctuation(location)
        if not location or location.lower() in action.lower():
            return ""

        lowered = action.lower()
        if any(verb in lowered for verb in _ARRIVAL_VERBS):
            return f" at the {location}"
        if any(verb in lowered for verb in _ENTRY_VERBS):
            return f" the {location}"
        return ""

    def _expression_phrase(self, event: Dict[str, Any]) -> str:
        expressions = event.get("expressions") or []
        if not isinstance(expressions, list):
            return ""
        for item in expressions:
            if not isinstance(item, dict):
                continue
            label = str(item.get("expression") or "").strip().lower()
            if label in _CONCRETE_EXPRESSIONS:
                return f", {_CONCRETE_EXPRESSIONS[label]}"
        return ""

    def format_event_description(self, event: Dict[str, Any]) -> str:
        """Compose one grounded, natural-language sentence from an event."""
        subject_phrase = self._subject_phrase(event)
        action_phrase = self._action_phrase(event, subject_phrase)

        if action_phrase.lower().startswith(subject_phrase.lower()):
            sentence = _capitalize(action_phrase)
        else:
            sentence = f"{subject_phrase} {action_phrase}"

        sentence += self._location_phrase(event, action_phrase)
        sentence += self._expression_phrase(event)

        sentence = _trim_to_words(_clean_text(sentence), self.max_words)
        return _ensure_sentence(sentence)

    def generate_descriptions(
        self,
        visual_events: Sequence[Dict[str, Any]],
        total_duration: float = 600.0,
    ) -> List[Dict[str, Any]]:
        """
        Generate contextual descriptions from visual events.

        Descriptions are ordered by event start time and carry continuity
        metadata plus a priority derived from the prioritization stage when
        available.
        """
        if not visual_events:
            return []

        context = self._get_previous_context()
        context_str = self._build_context_string(context)

        descriptions: List[Dict[str, Any]] = []
        for event in sorted(visual_events, key=lambda item: float(item.get("start", 0.0))):
            start = float(event.get("start", 0.0))
            end = float(event.get("end", start + 2.0))
            text = self.format_event_description(event)
            if not text:
                continue

            priority = float(
                event.get(
                    "importance_score",
                    event.get("priority", event.get("importance", 0.5)),
                )
            )
            descriptions.append(
                {
                    "id": str(event.get("id") or f"desc_{uuid.uuid4().hex[:12]}"),
                    "start": round(max(0.0, start), 2),
                    "end": round(min(total_duration, max(start, end)), 2),
                    "text": text,
                    "priority": round(max(0.0, min(1.0, priority)), 3),
                    "status": "PROPOSED",
                    "subject": event.get("subject"),
                    "action": event.get("action"),
                    "context": context_str,
                }
            )

        logger.info(
            "Contextual descriptions: %d generated with %s",
            len(descriptions),
            "continuity context" if context_str else "no prior context",
        )
        return descriptions

    def enrich_with_context(
        self,
        descriptions: Sequence[Dict[str, Any]],
        visual_events: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Attach continuity context to already-generated descriptions.

        When ``visual_events`` is provided, matching events (by nearest start
        time) supply a location/continuity hint. Text is only rewritten when
        the enriched form is strictly safer and grounded.
        """
        context = self._get_previous_context()
        context_str = self._build_context_string(context)
        events_by_start: List[Tuple[float, Dict[str, Any]]] = sorted(
            (
                (float(event.get("start", 0.0)), event)
                for event in (visual_events or [])
            ),
            key=lambda pair: pair[0],
        )

        enriched: List[Dict[str, Any]] = []
        for description in descriptions:
            item = dict(description)
            if context_str:
                item["context"] = context_str

            if events_by_start:
                start = float(item.get("start", 0.0))
                _, event = min(
                    events_by_start, key=lambda pair: abs(pair[0] - start)
                )
                location = str(event.get("location") or "").strip()
                if not location:
                    try:
                        scene_number = int(event.get("scene_number", -1))
                    except (TypeError, ValueError):
                        scene_number = -1
                    location = self._scene_locations.get(scene_number, "")
                if location:
                    item["location"] = _strip_trailing_punctuation(location)
            enriched.append(item)

        return enriched
