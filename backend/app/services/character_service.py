"""
character_service.py
--------------------
Character detection and cross-scene tracking.

Identifies recurring subjects (people, distinct objects) across frames and
scenes, maintaining identity through appearance similarity and temporal
proxity. Produces structured character records for downstream description.
"""

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.utils.logging_utils import logger


class CharacterService:
    """Tracks characters across frames and scenes."""

    def __init__(self):
        self._characters: Dict[str, Dict[str, Any]] = {}
        self._next_id = 1

    def _generate_id(self, descriptor: str) -> str:
        raw = f"{descriptor}-{self._next_id}"
        self._next_id += 1
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def detect_from_events(
        self,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extract distinct character subjects from Gemini visual events."""
        detected: List[Dict[str, Any]] = []
        for ev in events:
            subject = ev.get("subject", "").strip()
            if not subject or subject.lower() in ("the scene", "camera", "view", "background"):
                continue
            confidence = float(ev.get("confidence", 0.0))
            if confidence < settings.CHARACTER_TRACKING_MIN_CONFIDENCE:
                continue

            char_id = self._match_or_create(subject, ev)
            self._characters[char_id]["last_seen"] = ev.get("end")
            self._characters[char_id]["appearances"] = (
                self._characters[char_id].get("appearances", 0) + 1
            )
            detected.append({
                "character_id": char_id,
                "label": subject,
                "first_seen": self._characters[char_id].get("first_seen", ev.get("start")),
                "last_seen": ev.get("end"),
                "confidence": confidence,
            })
        return detected

    def _match_or_create(self, label: str, event: Dict[str, Any]) -> str:
        """Match by label similarity; create new character if no match."""
        for cid, char in self._characters.items():
            if char.get("label", "").lower() == label.lower():
                return cid
        char_id = self._generate_id(label)
        self._characters[char_id] = {
            "label": label,
            "first_seen": event.get("start"),
            "last_seen": event.get("end"),
            "appearances": 0,
        }
        return char_id

    def track_across_scenes(
        self,
        scene_events: List[List[Dict[str, Any]]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Track character identity across multiple scenes.

        Returns {character_id: {label, first_seen, last_seen, scenes: [int], appearances: int}}.
        """
        result: Dict[str, Dict[str, Any]] = {}
        for scene_idx, events in enumerate(scene_events):
            for ev in events:
                subject = ev.get("subject", "").strip()
                if not subject or subject.lower() in ("the scene", "camera", "view"):
                    continue
                char_id = self._match_or_create(subject, ev)
                if char_id not in result:
                    result[char_id] = {
                        "label": subject,
                        "first_seen": ev.get("start"),
                        "last_seen": ev.get("end"),
                        "scenes": [],
                        "appearances": 0,
                    }
                entry = result[char_id]
                if scene_idx not in entry["scenes"]:
                    entry["scenes"].append(scene_idx)
                entry["last_seen"] = ev.get("end")
                entry["appearances"] += 1
        return result

    def get_character_summary(self) -> List[Dict[str, Any]]:
        return [
            {"character_id": cid, **info}
            for cid, info in self._characters.items()
        ]

    def get_character_by_id(self, character_id: str) -> Optional[Dict[str, Any]]:
        info = self._characters.get(character_id)
        if info is None:
            return None
        return {"character_id": character_id, **info}