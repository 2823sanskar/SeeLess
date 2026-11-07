"""
tests/test_audio_mixing_service.py
----------------------------------
Unit and integration tests for Phase 4 Professional Audio Experience.

Verifies:
- EBU R128 loudness normalization (-24 LUFS target)
- Smart background ducking attenuation timing
- Multi-track FFmpeg muxing parameters
"""

import os
import pytest
import tempfile

from app.services.audio_mixing_service import (
    AudioMixingError,
    analyze_loudness,
    normalize_audio,
    build_ducking_volume_filter,
    AudioStemManager,
    mix_professional_audio,
)
from app.services.extraction_service import run_cmd
from app.services.audio_assembly_service import (
    create_separate_description_track,
    create_accessible_video,
)
from app.services.extraction_service import extract_metadata


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


@pytest.fixture
def synthetic_audio(temp_dir):
    """Create a 4-second synthetic stereo audio file with known level."""
    audio_path = os.path.join(temp_dir, "test_audio.wav")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration=4:sample_rate=44100",
        "-ac", "2",
        "-acodec", "pcm_s16le",
        audio_path
    ]
    run_cmd(cmd)
    return audio_path


@pytest.fixture
def synthetic_video_with_audio(temp_dir):
    """Create a 4-second synthetic video with audio track."""
    video_path = os.path.join(temp_dir, "test_video.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-c:a", "aac",
        video_path
    ]
    run_cmd(cmd)
    return video_path


class TestLoudnessAnalysis:
    def test_analyze_loudness_returns_valid_stats(self, synthetic_audio):
        stats = analyze_loudness(synthetic_audio)
        assert "input_i" in stats
        assert "input_tp" in stats
        assert "input_lra" in stats
        assert "input_thresh" in stats
        assert "target_offset" in stats
        assert stats["input_i"] > -30.0
        assert stats["input_tp"] > -25.0

    def test_analyze_loudness_raises_on_missing_file(self):
        with pytest.raises(AudioMixingError):
            analyze_loudness("/nonexistent/path/audio.wav")


class TestLoudnessNormalization:
    def test_normalize_audio_applies_loudnorm(self, synthetic_audio, temp_dir):
        output_path = os.path.join(temp_dir, "normalized.wav")
        normalize_audio(synthetic_audio, output_path)

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

        stats = analyze_loudness(output_path)
        assert abs(stats["input_i"] - (-24.0)) < 1.5

    def test_normalize_audio_custom_target_lufs(self, synthetic_audio, temp_dir):
        output_path = os.path.join(temp_dir, "normalized_custom.wav")
        normalize_audio(synthetic_audio, output_path, target_lufs=-16.0)

        stats = analyze_loudness(output_path)
        assert abs(stats["input_i"] - (-16.0)) < 1.5


class TestDuckingFilter:
    def test_build_ducking_filter_empty_clips_returns_unity(self):
        filter_str = build_ducking_volume_filter([], total_duration=10.0)
        assert filter_str == "volume=1.0"

    def test_build_ducking_filter_single_clip(self):
        clips = [{
            "scheduled_start": 1.0,
            "duration": 2.0,
            "actual_duration": 2.0,
        }]
        filter_str = build_ducking_volume_filter(clips, total_duration=10.0, ducking_gain_db=-12.0)
        assert "volume=eval=frame" in filter_str
        assert "if(" in filter_str
        assert "between(" in filter_str
        assert "0.251" in filter_str or "0.2512" in filter_str

    def test_build_ducking_filter_multiple_clips(self):
        clips = [
            {"scheduled_start": 1.0, "duration": 1.5, "actual_duration": 1.5},
            {"scheduled_start": 4.0, "duration": 1.0, "actual_duration": 1.0},
        ]
        filter_str = build_ducking_volume_filter(clips, total_duration=10.0, ducking_gain_db=-18.0)
        assert "volume=eval=frame" in filter_str
        assert "between(t,0.995,2.755)" in filter_str or "between(t,0.995,2.750)" in filter_str
        assert "0.126" in filter_str or "0.1259" in filter_str

    def test_build_ducking_filter_merge_overlapping(self):
        clips = [
            {"scheduled_start": 1.0, "duration": 3.0, "actual_duration": 3.0},
            {"scheduled_start": 2.0, "duration": 3.0, "actual_duration": 3.0},
        ]
        filter_str = build_ducking_volume_filter(clips, total_duration=10.0, ducking_gain_db=-12.0)
        assert filter_str.count("between(") == 1


class TestAudioStemManager:
    def test_create_narration_stem_empty(self, temp_dir):
        mgr = AudioStemManager(temp_dir)
        stem_path = mgr.create_narration_stem([], total_duration=4.0)
        assert os.path.exists(stem_path)
        stats = analyze_loudness(stem_path)
        assert stats["input_i"] < -70.0

    def test_create_narration_stem_with_clips(self, temp_dir, synthetic_audio):
        clip_path = os.path.join(temp_dir, "narration.wav")
        run_cmd([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-ac", "2", "-acodec", "pcm_s16le", clip_path
        ])

        clips = [{
            "description_id": "desc_1",
            "file_path": clip_path,
            "scheduled_start": 0.5,
            "duration": 1.0,
            "actual_duration": 1.0,
        }]

        mgr = AudioStemManager(temp_dir)
        stem_path = mgr.create_narration_stem(clips, total_duration=4.0, normalize=True)
        assert os.path.exists(stem_path)

        stats = analyze_loudness(stem_path)
        assert stats["input_i"] > -50.0

    def test_mix_master_track_simple(self, temp_dir, synthetic_audio):
        clip_path = os.path.join(temp_dir, "narration.wav")
        run_cmd([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-ac", "2", "-acodec", "pcm_s16le", clip_path
        ])

        clips = [{
            "description_id": "desc_1",
            "file_path": clip_path,
            "scheduled_start": 0.5,
            "duration": 1.0,
            "actual_duration": 1.0,
        }]

        mgr = AudioStemManager(temp_dir)
        output_path = mgr.mix_master_track(
            original_audio_path=synthetic_audio,
            narration_clips=clips,
            total_duration=4.0,
            enable_ducking=False,
            normalize_master=True,
        )
        assert os.path.exists(output_path)

        stats = analyze_loudness(output_path)
        assert abs(stats["input_i"] - (-24.0)) < 2.0

    def test_mix_master_track_with_ducking(self, temp_dir, synthetic_audio):
        clip_path = os.path.join(temp_dir, "narration.wav")
        run_cmd([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-ac", "2", "-acodec", "pcm_s16le", clip_path
        ])

        clips = [{
            "description_id": "desc_1",
            "file_path": clip_path,
            "scheduled_start": 1.0,
            "duration": 1.0,
            "actual_duration": 1.0,
        }]

        mgr = AudioStemManager(temp_dir)
        output_path = mgr.mix_master_track(
            original_audio_path=synthetic_audio,
            narration_clips=clips,
            total_duration=4.0,
            enable_ducking=True,
            ducking_gain_db=-12.0,
            normalize_master=True,
        )
        assert os.path.exists(output_path)

        stats = analyze_loudness(output_path)
        assert abs(stats["input_i"] - (-24.0)) < 2.0


class TestMixProfessionalAudioConvenience:
    def test_mix_professional_audio_function(self, temp_dir, synthetic_audio):
        clip_path = os.path.join(temp_dir, "narration.wav")
        run_cmd([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-ac", "2", "-acodec", "pcm_s16le", clip_path
        ])

        clips = [{
            "description_id": "desc_1",
            "file_path": clip_path,
            "scheduled_start": 0.5,
            "duration": 1.0,
            "actual_duration": 1.0,
        }]

        output_path = os.path.join(temp_dir, "master.aac")
        mix_professional_audio(
            original_audio_path=synthetic_audio,
            narration_clips=clips,
            output_audio_path=output_path,
            total_duration=4.0,
            enable_ducking=False,
        )
        assert os.path.exists(output_path)

        stats = analyze_loudness(output_path)
        assert abs(stats["input_i"] - (-24.0)) < 2.0


class TestEndToEndMultiTrackMuxing:
    def test_full_pipeline_audio_then_video_mux(self, temp_dir, synthetic_video_with_audio):
        orig_audio = os.path.join(temp_dir, "original_audio.wav")
        run_cmd(["ffmpeg", "-y", "-i", synthetic_video_with_audio, "-vn", orig_audio])

        clip_path = os.path.join(temp_dir, "narration.wav")
        run_cmd([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-ac", "2", "-acodec", "pcm_s16le", clip_path
        ])

        clips = [{
            "description_id": "desc_1",
            "file_path": clip_path,
            "scheduled_start": 1.0,
            "duration": 1.0,
            "actual_duration": 1.0,
        }]

        master_audio = os.path.join(temp_dir, "master.aac")
        mix_professional_audio(
            original_audio_path=orig_audio,
            narration_clips=clips,
            output_audio_path=master_audio,
            total_duration=4.0,
            enable_ducking=True,
            ducking_gain_db=-12.0,
        )
        assert os.path.exists(master_audio)

        ad_track = os.path.join(temp_dir, "ad_track.wav")
        create_separate_description_track(clips, ad_track, total_duration=4.0)
        assert os.path.exists(ad_track)

        final_video = os.path.join(temp_dir, "final.mp4")
        create_accessible_video(synthetic_video_with_audio, master_audio, final_video)
        assert os.path.exists(final_video)

        meta = extract_metadata(final_video)
        assert meta["has_audio"] is True
        assert meta["video_codec"] is not None
        assert meta["duration"] > 3.5 and meta["duration"] < 4.5


class TestVolumeNormalizationCurves:
    def test_loudnorm_curve_applies_correctly(self, temp_dir):
        input_path = os.path.join(temp_dir, "input.wav")
        run_cmd([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
            "-ac", "2", "-acodec", "pcm_s16le", input_path
        ])

        output_path = os.path.join(temp_dir, "output.wav")
        normalize_audio(input_path, output_path)

        stats1 = analyze_loudness(output_path)

        output_path2 = os.path.join(temp_dir, "output2.wav")
        normalize_audio(output_path, output_path2)
        stats2 = analyze_loudness(output_path2)

        assert abs(stats1["input_i"] - stats2["input_i"]) < 0.5
        assert abs(stats1["input_i"] - (-24.0)) < 1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])