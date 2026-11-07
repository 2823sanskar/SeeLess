import os
import json
import subprocess
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings
from app.utils.logging_utils import logger

class GnaniSTTError(Exception):
    pass

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0

def _call_gnani_stt_single(audio_path: str) -> Dict[str, Any]:
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
                timeout=60
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

def transcribe_audio_gnani_api(audio_path: str) -> Dict[str, Any]:
    """
    Transcribes audio using Gnani AI STT. If the audio is longer than 24 seconds,
    it automatically splits it into chunks (Gnani STT max limit is 30s) and joins them.
    """
    duration = get_audio_duration(audio_path)
    logger.info(f"Audio duration for STT: {duration:.2f}s")

    # If within 24 seconds, single call is fine
    if duration <= 24.0 or duration <= 0:
        return _call_gnani_stt_single(audio_path)

    chunk_size = 24.0
    transcripts = []
    combined_segments = []
    combined_words = []

    temp_dir = Path(audio_path).parent / "temp_stt_chunks"
    temp_dir.mkdir(parents=True, exist_ok=True)

    current_start = 0.0
    chunk_idx = 0

    while current_start < duration:
        actual_chunk_len = min(chunk_size, duration - current_start)
        chunk_file = temp_dir / f"chunk_{chunk_idx}.wav"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(current_start),
            "-t", str(actual_chunk_len),
            "-i", str(audio_path),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(chunk_file)
        ]

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            res = _call_gnani_stt_single(str(chunk_file))
            t_text = res.get("transcript", "").strip()
            if t_text:
                transcripts.append(t_text)

            if "segments" in res and isinstance(res["segments"], list):
                for s in res["segments"]:
                    combined_segments.append({
                        **s,
                        "start": round(float(s.get("start", 0.0)) + current_start, 2),
                        "end": round(float(s.get("end", 0.0)) + current_start, 2),
                    })
            elif t_text:
                w_count = len(t_text.split())
                combined_segments.append({
                    "start": round(current_start + 0.3, 2),
                    "end": round(min(duration, current_start + max(1.5, w_count * 0.4)), 2),
                    "text": t_text
                })

            if "words" in res and isinstance(res["words"], list):
                for w in res["words"]:
                    combined_words.append({
                        **w,
                        "start": round(float(w.get("start", 0.0)) + current_start, 2),
                        "end": round(float(w.get("end", 0.0)) + current_start, 2),
                    })
        except Exception as e:
            logger.warning(f"Error transcribing chunk {chunk_idx}: {e}")
        finally:
            if chunk_file.exists():
                try:
                    chunk_file.unlink()
                except Exception:
                    pass

        current_start += chunk_size
        chunk_idx += 1

    try:
        temp_dir.rmdir()
    except Exception:
        pass

    full_transcript = " ".join(transcripts).strip()
    return {
        "success": True,
        "transcript": full_transcript,
        "segments": combined_segments,
        "words": combined_words
    }

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
        words = transcription_result["words"]
        if words:
            curr_start = float(words[0].get("start", 0.0))
            curr_end = float(words[0].get("end", 0.0))
            curr_texts = [words[0].get("word", "")]

            for w in words[1:]:
                w_start = float(w.get("start", 0.0))
                w_end = float(w.get("end", 0.0))
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
    try:
        raw_res = transcribe_audio_gnani_api(audio_path)
    except Exception as e:
        logger.error(f"STT transcription failed with error: {e}. Falling back to empty segments.")
        raw_res = {"transcript": "", "segments": []}

    segments = extract_speech_segments(raw_res)

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
