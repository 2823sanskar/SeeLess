"""
workers/tasks.py
-----------------
Celery task + direct-call entry point for the SeeLess processing pipeline.

Pipeline stages:
  UPLOADING → EXTRACTING → ANALYZING_AUDIO → ANALYZING_VIDEO
  → GENERATING_DESCRIPTIONS → SCHEDULING_NARRATION
  → GENERATING_SPEECH → ASSEMBLING_AUDIO → QUALITY_CHECK → COMPLETED
"""
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Description,
    NarrationClip,
    ProcessingArtifact,
    ProcessingJob,
    Scene,
    SpeechSegment,
    Video,
    VisualEvent,
)
from app.services.audio_analysis_service import transcribe_audio
from app.services.audio_assembly_service import (
    assemble_audio,
    create_accessible_video,
    create_separate_description_track,
)
from app.services.context_service import ContextService
from app.services.description_service import generate_scene_descriptions
from app.services.extraction_service import extract_audio, extract_frames, validate_video
from app.services.quality_service import validate_accessible_output
from app.services.scene_service import detect_scenes
from app.services.scheduler_service import schedule_narration_clips, validate_clip_placement
from app.services.tts_service import generate_narration_audio, validate_narration_clip
from app.services.visual_analysis_service import analyze_visuals_for_video
from app.utils.file_utils import init_video_storage
from app.utils.logging_utils import logger
from app.workers.celery_app import celery_app


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _update_job(
    db: Session,
    job: ProcessingJob,
    status: str,
    step: str,
    progress: int,
    error: Optional[str] = None,
) -> None:
    job.status = status
    job.current_step = step
    job.progress = progress
    if error:
        job.error_message = error
    if status == "COMPLETED":
        job.completed_at = datetime.utcnow()
    db.commit()
    logger.info(f"[Job {job.id}] {status} | {step} ({progress}%)")


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def execute_video_pipeline(video_id: str) -> None:
    """
    Executes the full SeeLess processing pipeline for a given video_id.
    Can be called directly (BackgroundTasks) or via Celery (.delay).
    """
    db: Session = SessionLocal()

    video: Optional[Video] = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        logger.error(f"Pipeline aborted: Video '{video_id}' not found in database.")
        db.close()
        return

    job: Optional[ProcessingJob] = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id == video_id)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    if not job:
        job = ProcessingJob(
            video_id=video_id,
            status="RUNNING",
            current_step="Starting pipeline",
            progress=5,
        )
        db.add(job)
        db.commit()

    storage = init_video_storage(video_id)

    try:
        # ── Stage 1: Validate & extract ──────────────────────────────────────
        _update_job(db, job, "RUNNING", "Validating & extracting media", 10)

        video_path: str = video.original_file_path
        metadata: Dict = validate_video(video_path)
        video.duration = metadata["duration"]
        db.commit()

        with open(storage["extracted"] / "metadata.json", "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)

        audio_path: str = str(storage["extracted"] / "original_audio.wav")
        extract_audio(video_path, audio_path)

        frames: List[Dict] = extract_frames(video_path, str(storage["frames"]), fps=2.0)

        # ── Stage 2: Scene detection ──────────────────────────────────────────
        _update_job(db, job, "RUNNING", "Detecting scene boundaries", 25)

        scenes: List[Dict] = detect_scenes(video_path)
        for sc in scenes:
            db.add(Scene(
                video_id=video_id,
                scene_number=sc["scene_number"],
                start_time=sc["start_time"],
                end_time=sc["end_time"],
            ))
        db.commit()

        # ── Stage 3: Gnani AI STT – dialogue timeline ─────────────────────────
        _update_job(db, job, "RUNNING", "Transcribing dialogue with Gnani AI STT", 40)

        audio_analysis: Dict = transcribe_audio(audio_path)
        speech_segments: List[Dict] = audio_analysis["speech_segments"]
        protected_speech: List[Dict] = audio_analysis["protected_speech_intervals"]

        for sp in speech_segments:
            db.add(SpeechSegment(
                video_id=video_id,
                start_time=sp["start"],
                end_time=sp["end"],
                transcript=sp.get("text", ""),
            ))
        db.commit()

        with open(storage["analysis"] / "speech_segments.json", "w", encoding="utf-8") as fh:
            json.dump(speech_segments, fh, indent=2)

        # ── Stage 4: Gemini visual analysis ──────────────────────────────────
        _update_job(db, job, "RUNNING", "Analyzing visual events with Gemini", 55)

        ctx = ContextService()
        visual_events: List[Dict] = analyze_visuals_for_video(scenes, frames, ctx)

        for ev in visual_events:
            db.add(VisualEvent(
                video_id=video_id,
                start_time=ev["start"],
                end_time=ev["end"],
                event_description=f"{ev.get('subject', '')} {ev.get('action', '')}".strip(),
                subject=ev.get("subject"),
                importance=ev.get("importance", 0.5),
                confidence=ev.get("confidence", 1.0),
            ))
        db.commit()

        with open(storage["analysis"] / "visual_events.json", "w", encoding="utf-8") as fh:
            json.dump(visual_events, fh, indent=2)

        # ── Stage 5: Description generation ──────────────────────────────────
        _update_job(db, job, "RUNNING", "Generating visual descriptions", 65)

        descriptions: List[Dict] = generate_scene_descriptions(
            visual_events, ctx, total_duration=video.duration or 600.0
        )

        desc_records: Dict[str, Description] = {}
        for d in descriptions:
            obj = Description(
                id=d["id"],
                video_id=video_id,
                start_time=d["start"],
                end_time=d["end"],
                text=d["text"],
                priority=d.get("priority", 0.5),
                status="PROPOSED",
            )
            db.add(obj)
            desc_records[d["id"]] = obj
        db.commit()

        with open(storage["descriptions"] / "descriptions.json", "w", encoding="utf-8") as fh:
            json.dump(descriptions, fh, indent=2)

        # ── Stage 6: Narration scheduling ─────────────────────────────────────
        _update_job(db, job, "RUNNING", "Scheduling dialogue-safe narration", 75)

        schedule: Dict = schedule_narration_clips(
            descriptions, protected_speech, video_duration=video.duration or 600.0
        )

        with open(storage["descriptions"] / "schedule.json", "w", encoding="utf-8") as fh:
            json.dump(schedule, fh, indent=2)

        # ── Stage 7: Gnani AI TTS + revalidation ──────────────────────────────
        _update_job(db, job, "RUNNING", "Synthesizing narration with Gnani AI TTS", 85)

        valid_clips: List[Dict] = []
        for clip in schedule["scheduled"]:
            desc_id: str = clip["description_id"]
            clip_path: str = str(storage["narration"] / f"{desc_id}.wav")

            tts_result: Dict = generate_narration_audio(clip["text"], clip_path)
            actual_dur: float = tts_result["duration"]

            is_valid, sch_start, sch_end = validate_clip_placement(
                scheduled_start=clip["scheduled_start"],
                actual_duration=actual_dur,
                speech_intervals=protected_speech,
                video_duration=video.duration or 600.0,
            )

            if is_valid and validate_narration_clip(clip_path):
                db.add(NarrationClip(
                    description_id=desc_id,
                    audio_file_path=clip_path,
                    duration=actual_dur,
                    scheduled_start=sch_start,
                    scheduled_end=sch_end,
                    status="VALIDATED",
                ))
                if desc_id in desc_records:
                    desc_records[desc_id].status = "SCHEDULED"
                valid_clips.append({
                    "description_id": desc_id,
                    "file_path": clip_path,
                    "scheduled_start": sch_start,
                    "scheduled_end": sch_end,
                    "duration": actual_dur,
                    "text": clip["text"],
                })
            else:
                logger.warning(f"Clip '{desc_id}' dropped: post-TTS duration caused an overlap.")
                if desc_id in desc_records:
                    desc_records[desc_id].status = "OMITTED"

        db.commit()

        # ── Stage 8: Audio assembly & final render ────────────────────────────
        _update_job(db, job, "RUNNING", "Assembling accessible audio & rendering video", 92)

        mixed_path: str = str(storage["output"] / "mixed_soundtrack.aac")
        assemble_audio(audio_path, valid_clips, mixed_path, total_duration=video.duration or 600.0)

        ad_track_path: str = str(storage["output"] / "audio_description.wav")
        create_separate_description_track(valid_clips, ad_track_path, total_duration=video.duration or 600.0)

        final_video_path: str = str(storage["output"] / "accessible_video.mp4")
        create_accessible_video(video_path, mixed_path, final_video_path)

        # ── Stage 9: Quality validation ───────────────────────────────────────
        _update_job(db, job, "RUNNING", "Running quality assurance checks", 96)

        validate_accessible_output(
            video_path=final_video_path,
            audio_description_path=ad_track_path,
            original_duration=video.duration or 600.0,
            protected_speech_intervals=protected_speech,
            scheduled_clips=valid_clips,
        )

        # ── Persist artifacts ─────────────────────────────────────────────────
        db.add(ProcessingArtifact(video_id=video_id, artifact_type="accessible_video", file_path=final_video_path))
        db.add(ProcessingArtifact(video_id=video_id, artifact_type="audio_description", file_path=ad_track_path))

        transcript_path: str = str(storage["output"] / "transcript.json")
        with open(transcript_path, "w", encoding="utf-8") as fh:
            json.dump(speech_segments, fh, indent=2)
        db.add(ProcessingArtifact(video_id=video_id, artifact_type="transcript", file_path=transcript_path))

        video.status = "COMPLETED"
        _update_job(db, job, "COMPLETED", "Completed", 100)

    except Exception as exc:
        full_trace = traceback.format_exc()
        logger.error(f"Pipeline failure for video '{video_id}': {exc}\n{full_trace}")
        video.status = "FAILED"
        _update_job(db, job, "FAILED", "Pipeline failed", job.progress, error=str(exc))

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Celery entry point
# ---------------------------------------------------------------------------

@celery_app.task(name="app.workers.tasks.process_video_task")
def process_video_task(video_id: str) -> None:
    logger.info(f"Celery task received for video '{video_id}'.")
    execute_video_pipeline(video_id)
