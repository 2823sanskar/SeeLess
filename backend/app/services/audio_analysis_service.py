import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.logging_utils import logger

class GnaniSTTError(Exception):
    pass

def transcribe_audio_gnani_api(audio_path: str) -> Dict[str, Any]:
    """
    Calls Gnani AI STT REST endpoint to transcribe dialogue from original audio.
    """
    if not settings.GNANI_API_KEY:
        logger.warning("GNANI_API_KEY is not set. Gnani STT will return mock/empty transcription for testing.")
        return {
            "transcript": "",
            "segments": [],
            "status": "NO_API_KEY"
        }

    headers = {
        "X-API-Key-ID": settings.GNANI_API_KEY
    }
    
    data = {
        "model": settings.GNANI_STT_MODEL,
        "language_code": settings.GNANI_LANGUAGE_CODE,
        "format": "transcribe"
    }

    try:
        with open(audio_path, "rb") as f:
            files = {
                "audio_file": (Path(audio_path).name, f, "audio/wav")
            }
            logger.info(f"Sending audio to Gnani STT ({settings.GNANI_STT_ENDPOINT})...")
            response = requests.post(
                settings.GNANI_STT_ENDPOINT,
                headers=headers,
                data=data,
                files=files,
                timeout=90
            )

        if response.status_code != 200:
            logger.error(f"Gnani STT API error [{response.status_code}]: {response.text}")
            raise GnaniSTTError(f"Gnani STT request failed with code {response.status_code}: {response.text}")

        res_json = response.json()
        logger.info(f"Gnani STT response received: {res_json.get('request_id', 'ok')}")
        return res_json

    except Exception as e:
        logger.error(f"Gnani STT call failed: {e}")
        raise GnaniSTTError(str(e))

def extract_speech_segments(transcription_result: Dict[str, Any], safety_padding_sec: float = 0.2) -> List[Dict[str, Any]]:
    """
    Extracts speech segments from Gnani STT result and converts into standardized SeeLess schema:
    [{'start': float, 'end': float, 'text': str}]
    """
    speech_segments = []

    # Case 1: Result has 'segments' or 'words'
    if "segments" in transcription_result and isinstance(transcription_result["segments"], list):
        for seg in transcription_result["segments"]:
            s = max(0.0, float(seg.get("start", 0.0)) - safety_padding_sec)
            e = float(seg.get("end", 0.0)) + safety_padding_sec
            text = seg.get("text", "").strip()
            speech_segments.append({
                "start": round(s, 2),
                "end": round(e, 2),
                "text": text
            })
    elif "words" in transcription_result and isinstance(transcription_result["words"], list):
        # Group words into sentence-like intervals
        words = transcription_result["words"]
        if words:
            curr_start = float(words[0].get("start", 0.0))
            curr_end = float(words[0].get("end", 0.0))
            curr_texts = [words[0].get("word", "")]

            for w in words[1:]:
                w_start = float(w.get("start", 0.0))
                w_end = float(w.get("end", 0.0))
                # If gap > 0.8s between words, finalize segment
                if w_start - curr_end > 0.8:
                    speech_segments.append({
                        "start": round(max(0.0, curr_start - safety_padding_sec), 2),
                        "end": round(curr_end + safety_padding_sec, 2),
                        "text": " ".join(curr_texts).strip()
                    })
                    curr_start = w_start
                    curr_texts = []
                curr_end = w_end
                curr_texts.append(w.get("word", ""))

            if curr_texts:
                speech_segments.append({
                    "start": round(max(0.0, curr_start - safety_padding_sec), 2),
                    "end": round(curr_end + safety_padding_sec, 2),
                    "text": " ".join(curr_texts).strip()
                })
    elif transcription_result.get("transcript"):
        # If single transcript envelope is returned without word/segment breakdown
        # Use estimated segment duration based on audio duration or transcript length
        transcript_text = transcription_result["transcript"].strip()
        speech_segments.append({
            "start": 0.5,
            "end": max(2.0, len(transcript_text.split()) * 0.4 + 0.5),
            "text": transcript_text
        })

    return speech_segments

def validate_transcription(transcription_result: Dict[str, Any]) -> bool:
    if not transcription_result:
        return False
    return True

def save_transcription(video_id: str, transcription_result: Dict[str, Any], output_path: str):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcription_result, f, indent=2, ensure_ascii=False)

def transcribe_audio(audio_path: str) -> Dict[str, Any]:
    """
    Standardized STT interface returning normalized transcript and speech segments.
    """
    raw_res = transcribe_audio_gnani_api(audio_path)
    segments = extract_speech_segments(raw_res)
    
    # Generate protected speech intervals
    protected_intervals = []
    for s in segments:
        protected_intervals.append({
            "start": s["start"],
            "end": s["end"]
        })

    return {
        "raw": raw_res,
        "transcript": raw_res.get("transcript", ""),
        "speech_segments": segments,
        "protected_speech_intervals": protected_intervals
    }
