"""
narration_quality_service.py
-----------------------------
Post-generation narration quality checks.

Enforces conciseness, deduplication, continuity, and anti-speculation
constraints on generated audio descriptions before they reach the scheduler.
The service both rejects unsafe narration and repairs what can be repaired
safely (filler wording, overlong sentences, punctuation drift).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.config import settings
from app.utils.logging_utils import logger


class NarrationQualityError(Exception):
    """Raised when quality-check input is malformed."""


# Hedged language risks inventing visual content the model did not observe.
SPECULATIVE_PATTERNS: Tuple[str, ...] = (
    r"\bprobably\b", r"\bmaybe\b", r"\bperhaps\b", r"\bmight be\b",
    r"\bseems like\b", r"\bseems to\b", r"\bappears to be\b",
    r"\bcould be\b", r"\blikely\b", r"\bpossibly\b",
    r"\bi think\b", r"\bi believe\b", r"\bit looks like\b",
    r"\bit seems\b",
)

# Wordy phrases with concise replacements. Order matters (longest first).
WORDY_REWRITES: Tuple[Tuple[str, str], ...] = (
    (r"\bdue to the fact that\b", "because"),
    (r"\bat this point in time\b", "now"),
    (r"\bin the event that\b", "if"),
    (r"\bfor the purpose of\b", "to"),
    (r"\bin order to\b", "to"),
    (r"\bthe fact that\b", "that"),
    (r"\ba large number of\b", "many"),
    (r"\ba lot of\b", "many"),
    (r"\bvery much\b", ""),
    (r"\bat the present time\b", "now"),
    (r"\bprior to\b", "before"),
    (r"\bsubsequent to\b", "after"),
)

# Ideal spoken sentence length in words.
IDEAL_MIN_WORDS = 5
IDEAL_MAX_WORDS = 15

_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9']+")
_TRAILING_PUNCT_RE = re.compile(r"[.!?,;:\s]+$")
_LEADING_LABEL_RE = re.compile(r"^(description|narration)\s*:\s*", re.IGNORECASE)
_ELLIPSIS_RE = re.compile(r"\.{2,}|…")
_TRAILING_STOPWORDS = frozenset(
    {
        "and", "but", "or", "with", "to", "of", "in", "on", "at", "for",
        "the", "a", "an", "his", "her", "their", "as", "while", "then",
    }
)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class NarrationQualityService:
    """Validates and repairs narration quality before scheduling."""

    def __init__(
        self,
        max_words: Optional[int] = None,
        min_words: Optional[int] = None,
        max_duplicate_window: Optional[float] = None,
    ) -> None:
        self.max_words = int(max_words or settings.NARRATION_MAX_WORDS)
        self.min_words = int(min_words or settings.NARRATION_MIN_WORDS)
        self.max_duplicate_window = float(
            settings.NARRATION_DEDUP_WINDOW_SECONDS
            if max_duplicate_window is None
            else max_duplicate_window
        )
        self._speculative_re = tuple(
            re.compile(pattern, re.IGNORECASE)
            for pattern in SPECULATIVE_PATTERNS
        )

    # ------------------------------------------------------------------
    # Text normalization / repair
    # ------------------------------------------------------------------

    @staticmethod
    def _word_count(text: str) -> int:
        return len(text.strip().split())

    def normalize_text(self, text: str) -> str:
        """Normalize punctuation, whitespace, and filler wording."""
        cleaned = _WHITESPACE_RE.sub(" ", str(text or "")).strip()
        cleaned = _LEADING_LABEL_RE.sub("", cleaned)
        cleaned = _ELLIPSIS_RE.sub(".", cleaned)
        for pattern, replacement in WORDY_REWRITES:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip(" \"'`")
        cleaned = _TRAILING_PUNCT_RE.sub("", cleaned).strip()
        if not cleaned:
            return ""
        cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned + "."

    def shorten(self, text: str, max_words: Optional[int] = None) -> str:
        """Shorten a normalized sentence at a natural boundary."""
        budget = int(max_words or self.max_words)
        normalized = self.normalize_text(text)
        words = normalized.split()
        if len(words) <= budget:
            return normalized

        candidate = words[:budget]
        joined = " ".join(candidate)
        if "," in joined:
            head = joined.rsplit(",", 1)[0].strip()
            if len(head.split()) >= max(3, budget // 2):
                candidate = head.split()

        while candidate and candidate[-1].lower().strip(",.;:!?") in _TRAILING_STOPWORDS:
            candidate.pop()
        if not candidate:
            candidate = words[:budget]

        shortened = " ".join(candidate).rstrip(",.;:!? ")
        return self.normalize_text(shortened)

    def rewrite_wordy(self, text: str) -> str:
        """Replace verbose constructions with concise equivalents."""
        return self.normalize_text(text)

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _is_speculative(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self._speculative_re)

    def _is_wordy(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            re.search(pattern, lowered) for pattern, _ in WORDY_REWRITES
        )

    def _is_too_short(self, text: str) -> bool:
        return self._word_count(text) < self.min_words

    def _is_too_long(self, text: str) -> bool:
        return self._word_count(text) > self.max_words

    def _is_duplicate(
        self,
        a: Dict[str, Any],
        b: Dict[str, Any],
    ) -> bool:
        """Check if two descriptions describe the same moment."""
        text_a = str(a.get("text", "")).strip().lower()
        text_b = str(b.get("text", "")).strip().lower()
        if text_a and text_a == text_b:
            return True

        tokens_a = _tokens(text_a)
        tokens_b = _tokens(text_b)
        if tokens_a and tokens_b:
            union = tokens_a | tokens_b
            if union and len(tokens_a & tokens_b) / len(union) >= 0.85:
                return True

        same_subject = (
            str(a.get("subject") or "").strip().lower()
            == str(b.get("subject") or "").strip().lower()
            and bool(str(a.get("subject") or "").strip())
        )
        same_action = (
            str(a.get("action") or "").strip().lower()
            == str(b.get("action") or "").strip().lower()
            and bool(str(a.get("action") or "").strip())
        )
        if same_subject and same_action:
            delta = abs(float(a.get("start", 0.0)) - float(b.get("start", 0.0)))
            if delta <= self.max_duplicate_window:
                return True

        return False

    def _is_repetitive(
        self,
        descriptions: Sequence[Dict[str, Any]],
        index: int,
    ) -> bool:
        current = descriptions[index]
        return any(
            self._is_duplicate(current, descriptions[earlier])
            for earlier in range(index)
        )

    # ------------------------------------------------------------------
    # Public validation API
    # ------------------------------------------------------------------

    def validate_descriptions(
        self,
        descriptions: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validate descriptions against quality rules.

        Returns ``(valid, rejected)`` where each entry is a copy with
        normalized text and any rejection reasons attached.
        """
        valid: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        normalized: List[Dict[str, Any]] = []

        for description in descriptions:
            item = dict(description)
            item["text"] = self.normalize_text(str(item.get("text", "")))
            normalized.append(item)

        for index, item in enumerate(normalized):
            text = str(item.get("text", ""))
            reasons: List[str] = []

            if not text:
                reasons.append("empty_text")
            else:
                if self._is_too_short(text):
                    reasons.append(f"too_short ({self._word_count(text)} words)")
                if self._is_too_long(text):
                    reasons.append(f"too_long ({self._word_count(text)} words)")
                if self._is_speculative(text):
                    reasons.append("speculative_language")
                if self._is_wordy(text):
                    reasons.append("wordy_phrasing")
                if self._is_repetitive(normalized, index):
                    reasons.append("repetitive")

            if reasons:
                item["rejection_reasons"] = reasons
                rejected.append(item)
                logger.info(
                    "Quality reject: %s... reasons=%s", text[:60], reasons
                )
            else:
                valid.append(item)

        logger.info(
            "Narration quality: %d valid, %d rejected of %d.",
            len(valid),
            len(rejected),
            len(descriptions),
        )
        return valid, rejected

    def process_descriptions(
        self,
        descriptions: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Full quality pass: normalize, repair wordiness/length, then reject
        only what cannot be safely repaired.
        """
        repaired: List[Dict[str, Any]] = []
        for description in sorted(
            descriptions, key=lambda item: float(item.get("start", 0.0))
        ):
            item = dict(description)
            text = self.normalize_text(str(item.get("text", "")))
            if text and self._word_count(text) > self.max_words:
                text = self.shorten(text)
            item["text"] = text
            item["conciseness"] = round(self.conciseness_score(text), 3)
            repaired.append(item)

        valid: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        for index, item in enumerate(repaired):
            text = str(item.get("text", ""))
            reasons: List[str] = []

            if not text:
                reasons.append("empty_text")
            if text and self._is_too_short(text):
                reasons.append(f"too_short ({self._word_count(text)} words)")
            if text and self._is_speculative(text):
                reasons.append("speculative_language")
            if text and self._is_wordy(text):
                reasons.append("wordy_phrasing")
            if text and self._is_repetitive(repaired, index):
                reasons.append("repetitive")

            if reasons:
                item["rejection_reasons"] = reasons
                rejected.append(item)
            else:
                item["status"] = "VALIDATED"
                valid.append(item)

        logger.info(
            "Narration quality pass: %d valid, %d rejected of %d.",
            len(valid),
            len(rejected),
            len(descriptions),
        )
        return valid, rejected

    def deduplicate(
        self,
        descriptions: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Remove duplicate descriptions, keeping the earliest occurrence."""
        kept: List[Dict[str, Any]] = []
        for description in descriptions:
            if not any(self._is_duplicate(description, existing) for existing in kept):
                kept.append(dict(description))
        return kept

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def conciseness_score(self, text: str) -> float:
        """Return a 0.0-1.0 conciseness score. Higher is better."""
        words = self._word_count(self.normalize_text(text))
        if words == 0:
            return 0.0
        if IDEAL_MIN_WORDS <= words <= IDEAL_MAX_WORDS:
            return 1.0
        if words < IDEAL_MIN_WORDS:
            return max(0.0, words / float(IDEAL_MIN_WORDS))
        return max(0.0, 1.0 - (words - IDEAL_MAX_WORDS) / 10.0)

    def ground_check(self, text: str, visual_evidence: Sequence[str]) -> bool:
        """
        Verify a description is grounded in at least one piece of evidence.

        Uses token overlap rather than exact substring matching so natural
        rephrasings still count as grounded.
        """
        if not visual_evidence:
            return True
        text_tokens = _tokens(text)
        if not text_tokens:
            return False
        for evidence in visual_evidence:
            evidence_tokens = _tokens(str(evidence))
            if evidence_tokens and text_tokens & evidence_tokens:
                return True
        return False
