"""
video_service.py
----------------
Business-logic layer for Video and ProcessingJob records.
Keeps the API router thin; all DB operations live here.
"""
import math
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Description, ProcessingArtifact, ProcessingJob, SpeechSegment, Video
from app.schemas import VideoListResponse, VideoSummarySchema
from app.utils.logging_utils import logger


def get_video_or_404(db: Session, video_id: str) -> Video:
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")
    return video


def get_latest_job(db: Session, video_id: str) -> Optional[ProcessingJob]:
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id == video_id)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )


def create_pending_job(db: Session, video_id: str) -> ProcessingJob:
    job = ProcessingJob(
        video_id=video_id,
        status="PENDING",
        current_step="Uploaded",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_queued_job(db: Session, video_id: str) -> ProcessingJob:
    job = ProcessingJob(
        video_id=video_id,
        status="QUEUED",
        current_step="Queued for processing",
        progress=5,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_job_queued(db: Session, job: ProcessingJob) -> None:
    job.status = "QUEUED"
    job.current_step = "Queued for processing"
    job.progress = 5
    job.error_message = None
    db.commit()


def get_artifact_path(db: Session, video_id: str, artifact_type: str) -> Optional[str]:
    artifact = (
        db.query(ProcessingArtifact)
        .filter(
            ProcessingArtifact.video_id == video_id,
            ProcessingArtifact.artifact_type == artifact_type,
        )
        .first()
    )
    if artifact and Path(artifact.file_path).exists():
        return artifact.file_path
    return None


def format_timestamp(seconds: float, srt: bool = False) -> str:
    """Format seconds into WebVTT (HH:MM:SS.mmm) or SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    sep = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def generate_vtt_content(
    descriptions: List[Description],
    speech_segments: List[SpeechSegment],
) -> str:
    """Generate standard WebVTT subtitles containing descriptions and dialogue."""
    lines = ["WEBVTT", ""]
    cues = []
    for d in descriptions:
        cues.append({
            "start": d.start_time,
            "end": d.end_time,
            "text": f"[Audio Description] {d.text}",
        })
    for s in speech_segments:
        if s.transcript:
            cues.append({
                "start": s.start_time,
                "end": s.end_time,
                "text": s.transcript,
            })

    cues.sort(key=lambda c: (c["start"], c["end"]))

    for i, cue in enumerate(cues, 1):
        start_str = format_timestamp(cue["start"], srt=False)
        end_str = format_timestamp(cue["end"], srt=False)
        lines.append(str(i))
        lines.append(f"{start_str} --> {end_str}")
        lines.append(cue["text"])
        lines.append("")

    return "\n".join(lines)


def generate_srt_content(
    descriptions: List[Description],
    speech_segments: List[SpeechSegment],
) -> str:
    """Generate standard SubRip (SRT) subtitles containing descriptions and dialogue."""
    lines = []
    cues = []
    for d in descriptions:
        cues.append({
            "start": d.start_time,
            "end": d.end_time,
            "text": f"[Audio Description] {d.text}",
        })
    for s in speech_segments:
        if s.transcript:
            cues.append({
                "start": s.start_time,
                "end": s.end_time,
                "text": s.transcript,
            })

    cues.sort(key=lambda c: (c["start"], c["end"]))

    for i, cue in enumerate(cues, 1):
        start_str = format_timestamp(cue["start"], srt=True)
        end_str = format_timestamp(cue["end"], srt=True)
        lines.append(str(i))
        lines.append(f"{start_str} --> {end_str}")
        lines.append(cue["text"])
        lines.append("")

    return "\n".join(lines)


def list_videos(
    db: Session,
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> VideoListResponse:
    query = db.query(Video)

    if status and status.upper() != "ALL":
        query = query.filter(Video.status == status.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(Video.original_filename.ilike(term))

    total = query.count()

    order_col = getattr(Video, sort_by, Video.created_at)
    if sort_order.lower() == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    offset = max(0, (page - 1) * page_size)
    videos = query.offset(offset).limit(page_size).all()

    items: List[VideoSummarySchema] = []
    for v in videos:
        latest_job = get_latest_job(db, v.id)
        current_step = latest_job.current_step if latest_job else None
        progress = latest_job.progress if latest_job else (100 if v.status == "COMPLETED" else 0)

        desc_count = db.query(Description).filter(Description.video_id == v.id).count()
        speech_count = db.query(SpeechSegment).filter(SpeechSegment.video_id == v.id).count()

        artifacts = db.query(ProcessingArtifact).filter(ProcessingArtifact.video_id == v.id).all()
        artifact_types = {a.artifact_type for a in artifacts}

        items.append(
            VideoSummarySchema(
                id=v.id,
                batch_id=v.batch_id,
                original_filename=v.original_filename,
                duration=v.duration,
                status=v.status,
                created_at=v.created_at,
                updated_at=v.updated_at,
                current_step=current_step,
                progress=progress,
                description_count=desc_count,
                speech_segment_count=speech_count,
                has_accessible_video="accessible_video" in artifact_types,
                has_audio_description="audio_description" in artifact_types,
                has_transcript="transcript" in artifact_types,
            )
        )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return VideoListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def delete_video_and_storage(db: Session, video_id: str) -> None:
    video = get_video_or_404(db, video_id)
    from app.config import STORAGE_PATH
    video_dir = STORAGE_PATH / video_id
    if video_dir.exists() and video_dir.is_dir():
        try:
            shutil.rmtree(video_dir, ignore_errors=True)
        except Exception as exc:
            logger.warning(f"Could not remove directory {video_dir}: {exc}")

    db.delete(video)
    db.commit()


def create_bulk_export_zip(
    db: Session,
    video_ids: List[str],
    export_types: List[str],
) -> Tuple[str, int]:
    """Build a zip archive containing requested assets for the given videos. Returns (zip_path, file_count)."""
    temp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    temp_zip.close()

    total_files = 0
    with zipfile.ZipFile(temp_zip.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for vid in video_ids:
            video = db.query(Video).filter(Video.id == vid).first()
            if not video:
                continue

            folder_name = f"{video.original_filename.rsplit('.', 1)[0]}_{vid[:8]}"
            artifacts = db.query(ProcessingArtifact).filter(ProcessingArtifact.video_id == vid).all()
            art_map = {a.artifact_type: a.file_path for a in artifacts}

            descriptions = db.query(Description).filter(Description.video_id == vid).all()
            speech_segments = db.query(SpeechSegment).filter(SpeechSegment.video_id == vid).all()

            if "accessible_video" in export_types and "accessible_video" in art_map:
                fpath = art_map["accessible_video"]
                if Path(fpath).exists():
                    zf.write(fpath, f"{folder_name}/accessible_{video.original_filename}")
                    total_files += 1

            if "audio_description" in export_types and "audio_description" in art_map:
                fpath = art_map["audio_description"]
                if Path(fpath).exists():
                    zf.write(fpath, f"{folder_name}/audio_description.wav")
                    total_files += 1

            if "transcript" in export_types and "transcript" in art_map:
                fpath = art_map["transcript"]
                if Path(fpath).exists():
                    zf.write(fpath, f"{folder_name}/transcript.json")
                    total_files += 1

            if "vtt" in export_types and (descriptions or speech_segments):
                vtt_text = generate_vtt_content(descriptions, speech_segments)
                zf.writestr(f"{folder_name}/subtitles.vtt", vtt_text)
                total_files += 1

            if "srt" in export_types and (descriptions or speech_segments):
                srt_text = generate_srt_content(descriptions, speech_segments)
                zf.writestr(f"{folder_name}/subtitles.srt", srt_text)
                total_files += 1

    return temp_zip.name, total_files

