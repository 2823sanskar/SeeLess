"""
continuity_service.py
----------------------
Scene continuity — propagate context across scenes.

Maintains character presence, location state, and narrative thread so
downstream description generation can reference what happened before
instead of treating each scene as isolated.
"""

from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.logging_utils import logger


class ContinuityError(Exception):
    pass


class ContinuityService:
    """Tracks cross-scene continuity for description generation."""

    def __init__(self):
        self._scene_summaries: List[Dict[str, Any]] = []
        self._active_characters: Dict[str, Dict[str, Any]] = {}
        self._last_location: Optional[str] = None

    def record_scene(
        self,
        scene_number: int,
        events: List[Dict[str, Any]],
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a scene's events and return a continuity summary."""
        characters_present = []
        for ev in events:
            subject = ev.get("subject", "").strip()
            if subject and subject.lower() not in ("the scene", "camera", "view"):
                characters_present.append(subject)
                self._active_characters[subject] = {
                    "last_seen_scene": scene_number,
                    "last_seen_time": ev.get("end"),
                }

        summary = {
            "scene_number": scene_number,
            "characters_present": list(set(characters_present)),
            "event_count": len(events),
            "location": location or self._last_location,
            "start_time": events[0]["start"] if events else None,
            "end_time": events[-1]["end"] if events else None,
        }
        if location:
            self._last_location = location

        self._scene_summaries.append(summary)
        return summary

    def get_context_for_scene(
        self,
        scene_number: int,
    ) -> Dict[str, Any]:
        """Return continuity context for a given scene (previous scenes only)."""
        previous = [s for s in self._scene_summaries if s["scene_number"] < scene_number]
        if not previous:
            return {"previous_scenes": [], "active_characters": {}, "last_location": None}

        last = previous[-1]
        return {
            "previous_scenes": previous,
            "active_characters": dict(self._active_characters),
            "last_location": last.get("location"),
            "previous_scene_number": last["scene_number"],
        }

    def get_character_continuity(self) -> Dict[str, Dict[str, Any]]:
        """Return all tracked characters with their scene history."""
        return dict(self._active_characters)

    def reset(self) -> None:
        self._scene_summaries.clear()
        self._active_characters.clear()
        self._last_location = None