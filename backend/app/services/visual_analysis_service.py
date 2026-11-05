import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.logging_utils import logger
from app.services.context_service import ContextService

def clean_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()

def analyze_scene_frames_gemini(
    scene: Dict[str, Any],
    frames: List[Dict[str, Any]],
    context_service: Optional[ContextService] = None
) -> List[Dict[str, Any]]:
    """
    Analyzes frames for a scene using Gemini model.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not configured. Visual analysis with Gemini will return fallback visual events.")
        # Return fallback heuristic event
        return [{
            "start": scene["start_time"],
            "end": min(scene["end_time"], scene["start_time"] + 3.0),
            "subject": "The scene",
            "action": f"continues from {scene['start_time']}s to {scene['end_time']}s",
            "importance": 0.5,
            "confidence": 0.8
        }]

    import google.generativeai as genai
    from PIL import Image

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    # Filter frames belonging to scene
    scene_frames = [
        f for f in frames 
        if scene["start_time"] <= f["timestamp"] <= scene["end_time"]
    ]
    
    # Cap to max 8 frames per scene for rate/token efficiency
    if len(scene_frames) > 8:
        step = len(scene_frames) // 8
        scene_frames = scene_frames[::step][:8]

    if not scene_frames:
        return []

    images = []
    frame_descriptions = []
    for f in scene_frames:
        try:
            img = Image.open(f["file_path"])
            images.append(img)
            frame_descriptions.append(f"Frame at {f['timestamp']}s")
        except Exception as e:
            logger.error(f"Failed to load frame image {f['file_path']}: {e}")

    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "visual_analysis.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Analyze visual events in video frames."

    character_context_str = ""
    if context_service:
        ctx = context_service.get_context_summary()
        character_context_str = f"\nPrevious context: {json.dumps(ctx)}"

    user_query = f"""
Scene #{scene.get('scene_number', 1)} from {scene['start_time']}s to {scene['end_time']}s.
Frames provided: {', '.join(frame_descriptions)}.
{character_context_str}

Identify key visual events, actions, characters, and movements happening strictly on screen.
Output JSON only adhering to the format:
{{
  "scene_id": {scene.get('scene_number', 1)},
  "events": [
    {{
      "start": {scene['start_time']},
      "end": {min(scene['end_time'], scene['start_time'] + 3.0)},
      "subject": "Description of person/object",
      "action": "Description of action/movement",
      "importance": 0.8,
      "confidence": 0.95
    }}
  ]
}}
"""
    try:
        content_parts = [system_prompt, user_query] + images
        response = model.generate_content(content_parts)
        cleaned_json = clean_json_text(response.text)
        data = json.loads(cleaned_json)
        events = data.get("events", [])
        
        # Update context if characters mentioned
        if context_service:
            for ev in events:
                subj = ev.get("subject")
                if subj and subj.lower() not in ["the scene", "camera", "view"]:
                    context_service.update_character(subj, {"last_seen": ev.get("end")})

        return events
    except Exception as e:
        logger.error(f"Gemini visual analysis failed: {e}")
        # Return fallback event
        return [{
            "start": scene["start_time"],
            "end": min(scene["end_time"], scene["start_time"] + 2.5),
            "subject": "Visual action",
            "action": "unfolds on screen",
            "importance": 0.5,
            "confidence": 0.5
        }]

def analyze_visuals_for_video(
    scenes: List[Dict[str, Any]],
    frames: List[Dict[str, Any]],
    context_service: Optional[ContextService] = None
) -> List[Dict[str, Any]]:
    all_events = []
    if not context_service:
        context_service = ContextService()

    for sc in scenes:
        events = analyze_scene_frames_gemini(sc, frames, context_service)
        for ev in events:
            ev["scene_number"] = sc.get("scene_number", 1)
            all_events.append(ev)

    all_events.sort(key=lambda x: x["start"])
    return all_events

