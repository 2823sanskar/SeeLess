import pytest
from app.services.description_service import generate_scene_descriptions

def test_description_generation_rules():
    visual_events = [
        {
            "start": 2.0,
            "end": 4.5,
            "subject": "A woman",
            "action": "walks quickly to the window",
            "importance": 0.8
        },
        {
            "start": 10.0,
            "end": 12.0,
            "subject": "A shadowy figure",
            "action": "stands behind the curtain",
            "importance": 0.95
        }
    ]

    descriptions = generate_scene_descriptions(visual_events, total_duration=30.0)
    assert len(descriptions) == 2
    for d in descriptions:
        assert "start" in d
        assert "end" in d
        assert "text" in d
        assert len(d["text"]) > 0
        assert d["priority"] >= 0.0

def test_empty_events():
    descriptions = generate_scene_descriptions([], total_duration=10.0)
    assert descriptions == []

