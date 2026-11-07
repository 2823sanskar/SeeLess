import os
import random
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import settings
from app.utils.logging_utils import logger
from app.services.extraction_service import run_cmd

class GnaniTTSError(Exception):
    pass

class RetryPolicy:
    """Exponential backoff with jitter for external API calls."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        jitter: float = 0.5
    ):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.backoff_base * (2 ** attempt)
        jitter_range = delay * self.jitter
        return delay + random.uniform(-jitter_range, jitter_range)

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if request should be retried."""
        if attempt >= self.max_retries:
            return False
        # Retry on network errors, timeouts, and 429/5xx responses
        if isinstance(exception, (requests.Timeout, requests.ConnectionError)):
            return True
        if isinstance(exception, GnaniTTSError):
            # Check if it's a 429 or 5xx error
            error_str = str(exception)
            if "429" in error_str or any(f"{code}" in error_str for code in ["500", "502", "503", "504"]):
                return True
        return False

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    res = run_cmd(cmd)
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0

def validate_narration_clip(audio_path: str) -> bool:
    if not os.path.exists(audio_path):
        return False
    if os.path.getsize(audio_path) == 0:
        return False
    return get_audio_duration(audio_path) > 0.0

def generate_narration_audio_gnani(
    text: str,
    output_path: str,
    voice_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synthesizes narration text into speech exclusively using Gnani AI TTS.
    Implements exponential backoff with jitter for rate limit handling.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    voice = voice_id or settings.GNANI_VOICE_ID

    if not settings.GNANI_API_KEY:
        logger.warning("GNANI_API_KEY is not set. Generating synthetic test audio tone for testing purposes.")
        words = len(text.split())
        dur = max(1.5, words * 0.45)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=520:duration={dur}",
            "-ac", "1",
            "-ar", "24000",
            output_path
        ]
        run_cmd(cmd)
        return {
            "file_path": output_path,
            "duration": round(dur, 2),
            "text": text,
            "provider": "mock_tone_no_key"
        }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key-ID": settings.GNANI_API_KEY
    }

    payload = {
        "text": text,
        "voice": voice,
        "model": settings.GNANI_TTS_MODEL,
        "language": settings.GNANI_LANGUAGE_CODE,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 24000,
            "encoding": "linear_pcm",
            "container": "wav"
        }
    }

    retry_policy = RetryPolicy(
        max_retries=settings.GNANI_TTS_MAX_RETRIES,
        backoff_base=settings.GNANI_TTS_BACKOFF_BASE,
        jitter=settings.GNANI_TTS_JITTER
    )

    attempt = 0
    while True:
        try:
            logger.info(f"Sending narration to Gnani TTS for voice '{voice}' (attempt {attempt + 1})...")
            response = requests.post(
                settings.GNANI_TTS_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=60
            )

            if response.status_code != 200:
                error_msg = f"Gnani TTS API error [{response.status_code}]: {response.text}"
                logger.error(error_msg)
                raise GnaniTTSError(error_msg)

            # Save audio content
            with open(output_path, "wb") as f:
                f.write(response.content)

            dur = get_audio_duration(output_path)
            logger.info(f"Gnani TTS clip generated successfully. Duration: {dur}s")

            return {
                "file_path": output_path,
                "duration": round(dur, 2),
                "text": text,
                "provider": "gnani_ai"
            }

        except Exception as e:
            logger.warning(f"Gnani TTS generation error (attempt {attempt + 1}): {e}")

            if retry_policy.should_retry(attempt, e):
                delay = retry_policy.get_delay(attempt)
                logger.info(f"Retrying in {delay:.2f}s...")
                time.sleep(delay)
                attempt += 1
                continue

            # Max retries exhausted or non-retryable error
            logger.error(f"Gnani TTS generation failed after {attempt + 1} attempts: {e}")
            raise GnaniTTSError(str(e))

def generate_narration_audio(
    text: str,
    output_path: str,
    voice_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Standard interface to generate narration audio.
    """
    return generate_narration_audio_gnani(text, output_path, voice_id)