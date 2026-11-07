"""
prioritization_service.py
--------------------------
Event prioritization for the SeeLess narration engine.

Scores visual events by narrative importance (plot-critical actions rank
above routine movement), removes duplicate/redundant descriptions, filters
speculative language, and provides demotion helpers used when schedule
space is constrained.

Public API is intentionally deterministic and side-effect free so the
scheduler can rely on stable priorities.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.config import settings
from app.utils.logging_utils import logger


class PrioritizationError(Exception):
    """Raised when prioritization input is malformed."""


# Actions that usually move the story forward. A match raises the floor of
# the importance score because missing these events harms comprehension.
HIGH_IMPORTANCE_ACTIONS: Set[str] = {
    "weapon", "gun", "knife", "draws", "aims", "attack", "attacks", "fights",
    "hits", "strikes", "kicks", "runs", "flees", "escapes", "chases",
    "enters", "exits", "leaves", "arrives", "opens", "closes", "locks",
    "reveals", "discovers", "finds", "grabs", "takes", "gives", "throws",
    "falls", "collapses", "dies", "kisses", "embraces", "cries", "shouts",
    "turns", "faces", "reaches", "drops", "crashes", "explodes",
}

# Actions that are visible but usually not worth narrating.
LOW_IMPORTANCE_ACTIONS: Set[str] = {
    "blinks", "breathes", "sighs", "glances", "shifts", "adjusts", "fidgets",
    "stands", "sits", "waits", "looks_around", "nods", "shrugs",
    "tilts_head", "smiles_neutral", "scratches", "taps",
}

# Vague subjects make a description less actionable for a viewer.
VAGUE_SUBJECTS: Set[str] = {
    "a person", "someone", "a figure", "the figure", "people",
    "a character", "the character", "something",
}

# Hedged language risks inventing visual content the model did not observe.
SPECULATIVE_PATTERNS: Tuple[str, ...] = (
    r"\bprobably\b", r"\bmaybe\b", r"\bperhaps\b", r"\bmight be\b",
    r"\bseems like\b", r"\bseems to\b", r"\bappears to be\b",
    r"\bcould be\b", r"\blikely\b", r"\bpossibly\b",
    r"\bi think\b", r"\bi believe\b", r"\bit looks like\b",
)

_SPECULATIVE_RE = tuple(re.compile(p, re.IGNORECASE) for p in SPECULATIVE_PATTERNS)
_TOKEN_RE = re.compile(r"[a-z0-9']+")

_EPSILON = 1e-6


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalized_action(event: Dict[str, Any]) -> str:
    action = str(event.get("action") or "").strip().lower()
    return re.sub(r"[\s\-]+", "_", action)


def _event_text(event: Dict[str, Any]) -> str:
    """Best-effort textual representation of an event for filters/dedup."""
    for key in ("text", "description", "event_description", "narration"):
        value = event.get(key)
        if value:
            return str(value).strip()
    subject = str(event.get("subject") or "").strip()
    action = str(event.get("action") or "").strip()
    return f"{subject} {action}".strip()


def _tokens(text: str) -> Set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def is_speculative(text: str) -> bool:
    """Return True when text contains hedged/speculative language."""
    lowered = text.lower()
    return any(pattern.search(lowered) for pattern in _SPECULATIVE_RE)


def score_event(event: Dict[str, Any]) -> float:
    """
    Score an event's narrative importance in the range 0.0-1.0.

    The score blends the event's declared importance, action semantics,
    detection confidence, subject specificity, and available visual
    enrichment (expressions, background events).
    """
    raw_importance = event.get("importance", event.get("priority", 0.5))
    try:
        score = float(raw_importance)
    except (TypeError, ValueError):
        score = 0.5
    score = _clamp(score)

    action = _normalized_action(event)
    subject = str(event.get("subject") or "").strip().lower()

    high_hits = [keyword for keyword in HIGH_IMPORTANCE_ACTIONS if keyword in action]
    if high_hits:
        # Plot-relevant beats routine movement even when the model was unsure.
        score = max(score, 0.85)
        score = min(1.0, score + 0.05 * min(len(high_hits), 2))

    low_hits = [keyword for keyword in LOW_IMPORTANCE_ACTIONS if keyword in action]
    if low_hits and not high_hits:
        score = min(score, 0.3)

    if subject in VAGUE_SUBJECTS:
        score *= 0.85

    # Confidence acts as a gentle multiplier; low-confidence events should
    # not outrank confident ones with the same declared importance.
    try:
        confidence = _clamp(float(event.get("confidence", 1.0)))
    except (TypeError, ValueError):
        confidence = 1.0
    score *= 0.7 + 0.3 * confidence

    expressions = event.get("expressions") or []
    if expressions and any(
        str(e.get("expression", "")).lower() not in ("", "neutral", "unknown")
        for e in expressions
        if isinstance(e, dict)
    ):
        score += 0.05

    if event.get("background_events"):
        # Background events matter, but less than foreground action.
        score -= 0.05

    return round(_clamp(score), 3)


def _is_duplicate(
    a: Dict[str, Any],
    b: Dict[str, Any],
    window_seconds: float,
) -> bool:
    """Return True when two events describe the same visual moment."""
    text_a = _event_text(a)
    text_b = _event_text(b)
    if text_a and text_a.lower() == text_b.lower():
        return True

    tokens_a = _tokens(text_a)
    tokens_b = _tokens(text_b)
    if tokens_a and tokens_b:
        union = tokens_a | tokens_b
        similarity = len(tokens_a & tokens_b) / len(union) if union else 1.0
        if similarity >= 0.85:
            return True

    same_subject = (
        str(a.get("subject") or "").strip().lower()
        == str(b.get("subject") or "").strip().lower()
        and bool(str(a.get("subject") or "").strip())
    )
    same_action = (
        _normalized_action(a) == _normalized_action(b)
        and bool(_normalized_action(a))
    )
    if same_subject and same_action:
        try:
            delta = abs(float(a.get("start", 0.0)) - float(b.get("start", 0.0)))
        except (TypeError, ValueError):
            delta = 0.0
        if delta <= window_seconds:
            return True

    return False


def filter_speculative(
    descriptions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remove descriptions whose text contains speculative language."""
    filtered: List[Dict[str, Any]] = []
    for description in descriptions:
        text = _event_text(description)
        if text and is_speculative(text):
            logger.info("Filtering speculative description: %s...", text[:60])
            continue
        filtered.append(dict(description))
    return filtered


def prioritize_events(
    events: Sequence[Dict[str, Any]],
    max_descriptions: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Score, deduplicate, filter, and rank visual events by importance.

    Returns copies sorted by importance score descending (ties broken by
    start time). Each copy carries ``importance_score`` and ``priority`` so
    downstream stages can sort without recomputing.
    """
    if not events:
        return []

    window = float(settings.NARRATION_DEDUP_WINDOW_SECONDS)
    scored: List[Dict[str, Any]] = []
    for event in events:
        item = dict(event)
        item["importance_score"] = score_event(item)
        item["priority"] = float(
            item.get("priority", item["importance_score"])
        )
        scored.append(item)

    deduped: List[Dict[str, Any]] = []
    for event in scored:
        if not any(
            _is_duplicate(event, existing, window) for existing in deduped
        ):
            deduped.append(event)

    if settings.NARRATION_FILTER_SPECULATIVE:
        deduped = filter_speculative(deduped)

    deduped.sort(
        key=lambda item: (-item["importance_score"], float(item.get("start", 0.0)))
    )

    cap = (
        max_descriptions
        if max_descriptions is not None
        else int(settings.NARRATION_MAX_DESCRIPTIONS)
    )
    if cap > 0 and len(deduped) > cap:
        logger.info(
            "Prioritization: capping %d events to %d", len(deduped), cap
        )
        deduped = deduped[:cap]

    logger.info(
        "Prioritization: %d events -> %d after scoring/dedup/filter",
        len(events),
        len(deduped),
    )
    return deduped


def rank_by_importance(
    descriptions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Rank descriptions by priority descending, then start time."""
    return sorted(
        (dict(item) for item in descriptions),
        key=lambda item: (
            -float(item.get("priority", item.get("importance_score", 0.5))),
            float(item.get("start", 0.0)),
        ),
    )


def demote_low_priority(
    descriptions: Sequence[Dict[str, Any]],
    available_slots: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split descriptions into kept (highest priority) and dropped when the
    schedule cannot hold everything.

    Returns ``(kept, dropped)``.
    """
    if available_slots < 0:
        raise PrioritizationError("available_slots must be non-negative")
    if not descriptions:
        return [], []

    ranked = rank_by_importance(descriptions)
    if len(ranked) <= available_slots:
        return ranked, []

    kept = ranked[:available_slots]
    dropped = ranked[available_slots:]
    logger.info(
        "Demotion: kept %d, dropped %d of %d",
        len(kept),
        len(dropped),
        len(ranked),
    )
    return kept, dropped
