from typing import Dict, Any, List

class ContextService:
    def __init__(self):
        self.characters: Dict[str, Dict[str, Any]] = {}
        self.last_scene_context: Dict[str, Any] = {}

    def update_character(self, name_or_tag: str, details: Dict[str, Any]):
        if name_or_tag not in self.characters:
            self.characters[name_or_tag] = details
        else:
            self.characters[name_or_tag].update(details)

    def get_character_context(self) -> List[Dict[str, Any]]:
        return list(self.characters.values())

    def update_scene_context(self, scene_id: str, summary: Dict[str, Any]):
        self.last_scene_context = {
            "scene_id": scene_id,
            **summary
        }

    def get_context_summary(self) -> Dict[str, Any]:
        return {
            "characters": self.characters,
            "last_scene": self.last_scene_context
        }

