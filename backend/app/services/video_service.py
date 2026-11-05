"""
video_service.py
----------------
Business-logic layer for Video and ProcessingJob records.
Keeps the API router thin; all DB operations live here.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.models import Video, ProcessingJob, ProcessingArtifact
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

