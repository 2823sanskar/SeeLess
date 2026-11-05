import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import init_db, SessionLocal
from app.models import Video, ProcessingJob
from app.workers.tasks import execute_video_pipeline
from app.services.extraction_service import run_cmd

def run_test():
    print("=== Testing End-to-End Processing Pipeline ===")
    init_db()

    # Create synthetic test MP4 video with audio tone
    test_dir = Path(__file__).resolve().parent.parent / "storage" / "test_run"
    test_dir.mkdir(parents=True, exist_ok=True)
    sample_video = str(test_dir / "sample_input.mp4")

    print("Generating synthetic 6-second video...")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=6",
        "-c:v", "libx264", "-c:a", "aac",
        sample_video
    ]
    run_cmd(cmd)
    print(f"Sample video created: {sample_video}")

    # Create video record in DB
    db = SessionLocal()
    vid = Video(
        original_filename="sample_input.mp4",
        original_file_path=sample_video,
        status="UPLOADED"
    )
    db.add(vid)
    db.commit()
    db.refresh(vid)
    video_id = vid.id
    db.close()

    print(f"Running pipeline for video ID: {video_id}...")
    execute_video_pipeline(video_id)

    # Verify results
    db = SessionLocal()
    updated_vid = db.query(Video).filter(Video.id == video_id).first()
    job = db.query(ProcessingJob).filter(ProcessingJob.video_id == video_id).first()

    print(f"\nFinal Video Status: {updated_vid.status}")
    print(f"Final Job Step: {job.current_step} ({job.progress}%)")
    if job.error_message:
        print(f"Error Message: {job.error_message}")

    output_dir = Path(__file__).resolve().parent.parent / "storage" / video_id / "output"
    final_video = output_dir / "accessible_video.mp4"
    ad_track = output_dir / "audio_description.wav"
    transcript = output_dir / "transcript.json"

    print("\nGenerated Artifacts:")
    print(f"Accessible Video ({final_video.name}): {'EXISTS' if final_video.exists() else 'MISSING'}")
    print(f"Audio Description Track ({ad_track.name}): {'EXISTS' if ad_track.exists() else 'MISSING'}")
    print(f"Transcript JSON ({transcript.name}): {'EXISTS' if transcript.exists() else 'MISSING'}")

    assert updated_vid.status == "COMPLETED", "Pipeline did not reach COMPLETED status"
    assert final_video.exists(), "Final accessible MP4 is missing"
    assert ad_track.exists(), "Audio description WAV is missing"
    print("\n✓ SUCCESS: End-to-end video pipeline executed successfully!")

if __name__ == "__main__":
    run_test()

