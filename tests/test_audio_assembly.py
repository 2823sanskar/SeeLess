import os
import pytest
from app.services.audio_assembly_service import assemble_audio, create_accessible_video, create_separate_description_track
from app.services.tts_service import generate_narration_audio
from app.services.extraction_service import run_cmd, extract_metadata

def test_audio_assembly_and_video(tmp_path):
    # Create 4-second synthetic test video with audio
    test_video = str(tmp_path / "input.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
        "-c:v", "libx264", "-c:a", "aac",
        test_video
    ]
    run_cmd(cmd)
    assert os.path.exists(test_video)

    # Original audio
    test_orig_audio = str(tmp_path / "original_audio.wav")
    run_cmd(["ffmpeg", "-y", "-i", test_video, "-vn", test_orig_audio])

    # Narration clip
    narration_wav = str(tmp_path / "desc_1.wav")
    generate_narration_audio("A test description.", narration_wav)

    narration_clips = [{
        "description_id": "desc_1",
        "file_path": narration_wav,
        "scheduled_start": 0.5,
        "scheduled_end": 2.0,
        "duration": 1.5,
        "text": "A test description."
    }]

    mixed_audio = str(tmp_path / "mixed.aac")
    assemble_audio(test_orig_audio, narration_clips, mixed_audio, total_duration=4.0)
    assert os.path.exists(mixed_audio)

    sep_ad = str(tmp_path / "ad_track.wav")
    create_separate_description_track(narration_clips, sep_ad, total_duration=4.0)
    assert os.path.exists(sep_ad)

    final_video = str(tmp_path / "accessible_output.mp4")
    create_accessible_video(test_video, mixed_audio, final_video)
    assert os.path.exists(final_video)

    meta = extract_metadata(final_video)
    assert meta["has_audio"] is True
    assert meta["video_codec"] is not None

