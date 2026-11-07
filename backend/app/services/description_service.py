import os
import json
import uuid
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

def generate_scene_descriptions(
    visual_events: List[Dict[str, Any]],
    context_service: Optional[ContextService] = None,
    total_duration: float = 600.0
) -> List[Dict[str, Any]]:
    """
    Generates concise, visual-only audio descriptions for visually impaired viewers based on visual events.
    Does NOT receive dialogue transcripts as content to paraphrase.
    """
    if not visual_events:
        return []

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is missing. Generating fallback descriptions from visual events directly.")
        fallback_descriptions = []
        for ev in visual_events:
            subj = ev.get("subject", "A figure")
            act = ev.get("action", "moves")
            desc_text = f"{subj} {act}."
            fallback_descriptions.append({
                "id": str(uuid.uuid4()),
                "start": ev["start"],
                "end": min(total_duration, ev["end"]),
                "text": desc_text,
                "priority": ev.get("importance", 0.7),
                "status": "PROPOSED"
            })
        return fallback_descriptions

    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "description_generation.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Write concise audio description sentences."

    ctx_info = ""
    if context_service:
        ctx_info = f"\nCharacter Context: {json.dumps(context_service.get_context_summary())}"

    user_query = f"""
Visual Events Timeline:
{json.dumps(visual_events, indent=2)}
{ctx_info}

Produce concise audio descriptions following all strict rules.
Output valid JSON only matching the schema:
{{
  "descriptions": [
    {{
      "start": 8.0,
      "end": 10.5,
      "text": "A man in a blue jacket enters the room.",
      "priority": 0.9
    }}
  ]
}}
"""
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[system_prompt, user_query]
        )
        cleaned_json = clean_json_text(response.text)
        data = json.loads(cleaned_json)
        descriptions = data.get("descriptions", [])

        results = []
        for d in descriptions:
            results.append({
                "id": str(uuid.uuid4()),
                "start": round(float(d.get("start", 0.0)), 2),
                "end": round(min(total_duration, float(d.get("end", 0.0))), 2),
                "text": d.get("text", "").strip(),
                "priority": float(d.get("priority", 0.5)),
                "status": "PROPOSED"
            })
        return results
    except Exception as e:
        logger.error(f"Gemini description generation failed: {e}. Falling back to visual events text.")
        fallback = []
        for ev in visual_events:
            subj = ev.get("subject", "A figure")
            act = ev.get("action", "appears")
            fallback.append({
                "id": str(uuid.uuid4()),
                "start": ev["start"],
                "end": min(total_duration, ev["end"]),
                "text": f"{subj} {act}.".strip(),
                "priority": ev.get("importance", 0.5),
                "status": "PROPOSED"
            })
        return fallback