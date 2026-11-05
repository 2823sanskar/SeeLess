import os
import pytest
from app.services.audio_analysis_service import (
    transcribe_audio,
    extract_speech_segments,
    validate_transcription,
    save_transcription
)
from app.services.extraction_service import run_cmd

def test_transcription_normalization_and_validation():
    sample_gnani_response = {
        "request_id": "req_123",
        "transcript": "Where have you been? I was waiting for you.",
        "segments": [
            {"start": 1.2, "end": 3.4, "text": "Where have you been?"},
            {"start": 4.0, "end": 6.5, "text": "I was waiting for you."}
        ]
    }

    assert validate_transcription(sample_gnani_response) is True
    segments = extract_speech_segments(sample_gnani_response)
    assert len(segments) == 2
    assert segments[0]["text"] == "Where have you been?"
    assert segments[0]["start"] <= 1.2  # safety padding applied
    assert segments[0]["end"] >= 3.4

def test_audio_analysis_synthetic(tmp_path):
    # Generate 3-second audio wave
    audio_path = str(tmp_path / "test_tone.wav")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=3",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]
    run_cmd(cmd)

    res = transcribe_audio(audio_path)
    assert "transcript" in res
    assert "speech_segments" in res
    assert "protected_speech_intervals" in res
    assert isinstance(res["protected_speech_intervals"], list)

    out_file = str(tmp_path / "transcription.json")
    save_transcription("test_vid", res, out_file)
    assert os.path.exists(out_file)
