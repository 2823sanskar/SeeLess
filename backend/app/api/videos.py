"""
api/videos.py
-------------
REST endpoints for video upload, processing, status, result and download.
Delegates DB logic to video_service; delegates processing to Celery / BackgroundTasks.
"""
import shutil
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Description, ProcessingArtifact, SpeechSegment, Video
from app.schemas import (
    DescriptionSchema,
    ProcessingStatusResponse,
    SpeechSegmentSchema,
    VideoResultResponse,
    VideoUploadResponse,
)
from app.services.extraction_service import validate_video
from app.services.video_service import (
    create_pending_job,
    create_queued_job,
    get_artifact_path,
    get_latest_job,
    get_video_or_404,
    mark_job_queued,
)
from app.utils.file_utils import init_video_storage, sanitize_filename
from app.utils.logging_utils import logger

router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.post("/upload", response_model=VideoUploadResponse, status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoUploadResponse:
    if Path(file.filename or "").suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="Only MP4 video files are supported.")

    safe_name = sanitize_filename(file.filename or "upload.mp4")
    new_video = Video(original_filename=safe_name, original_file_path="", status="UPLOADED")
    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    storage_paths = init_video_storage(new_video.id)
    dest_path = storage_paths["original"] / safe_name

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        db.delete(new_video)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}") from exc

    new_video.original_file_path = str(dest_path.resolve())

    try:
        meta = validate_video(new_video.original_file_path)
        new_video.duration = meta["duration"]
    except Exception as exc:
        logger.warning(f"Pre-validation warning for '{safe_name}': {exc}")

    job = create_pending_job(db, new_video.id)

    return VideoUploadResponse(
        video_id=new_video.id,
        job_id=job.id,
        status="UPLOADED",
        filename=safe_name,
    )


@router.post("/{video_id}/process")
async def start_processing(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    video = get_video_or_404(db, video_id)
    latest_job = get_latest_job(db, video_id)

    if latest_job and latest_job.status == "RUNNING":
        return {"video_id": video_id, "job_id": latest_job.id, "status": "ALREADY_RUNNING"}

    if not latest_job or latest_job.status in {"COMPLETED", "FAILED"}:
        job = create_queued_job(db, video_id)
    else:
        mark_job_queued(db, latest_job)
        job = latest_job

    celery_dispatched = False
    try:
        from app.workers.tasks import process_video_task  # lazy import avoids circular deps
        process_video_task.delay(video_id)
        celery_dispatched = True
        logger.info(f"Video {video_id} dispatched to Celery.")
    except Exception as exc:
        logger.warning(f"Celery unavailable ({exc}). Falling back to BackgroundTasks.")
        from app.workers.tasks import execute_video_pipeline
        background_tasks.add_task(execute_video_pipeline, video_id)

    return {
        "video_id": video_id,
        "job_id": job.id,
        "status": "PROCESSING_STARTED",
        "mode": "celery" if celery_dispatched else "background_task",
    }


@router.get("/{video_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(
    video_id: str,
    db: Session = Depends(get_db),
) -> ProcessingStatusResponse:
    video = get_video_or_404(db, video_id)
    job = get_latest_job(db, video_id)

    if not job:
        return ProcessingStatusResponse(
            video_id=video_id,
            status=video.status,
            current_step="Uploaded",
            progress=0,
            error=None,
        )

    return ProcessingStatusResponse(
        video_id=video_id,
        status=job.status,
        current_step=job.current_step,
        progress=job.progress,
        error=job.error_message,
    )


@router.get("/{video_id}/result", response_model=VideoResultResponse)
async def get_video_result(
    video_id: str,
    db: Session = Depends(get_db),
) -> VideoResultResponse:
    video = get_video_or_404(db, video_id)
    job = get_latest_job(db, video_id)
    status = job.status if job else video.status

    artifacts = db.query(ProcessingArtifact).filter(ProcessingArtifact.video_id == video_id).all()
    artifact_map = {a.artifact_type: a for a in artifacts}

    final_video_url = f"/api/videos/{video_id}/stream/video" if "accessible_video" in artifact_map else None
    audio_description_url = f"/api/videos/{video_id}/stream/audio" if "audio_description" in artifact_map else None
    transcript_url = f"/api/videos/{video_id}/stream/transcript" if "transcript" in artifact_map else None

    descriptions = db.query(Description).filter(Description.video_id == video_id).all()
    speech_segments = db.query(SpeechSegment).filter(SpeechSegment.video_id == video_id).all()

    return VideoResultResponse(
        video_id=video_id,
        status=status,
        final_video_url=final_video_url,
        audio_description_url=audio_description_url,
        transcript_url=transcript_url,
        descriptions=[
            DescriptionSchema(
                id=d.id, start=d.start_time, end=d.end_time,
                text=d.text, priority=d.priority, status=d.status,
            )
            for d in descriptions
        ],
        speech_segments=[
            SpeechSegmentSchema(start=s.start_time, end=s.end_time, text=s.transcript)
            for s in speech_segments
        ],
    )


@router.get("/{video_id}/download")
async def download_accessible_video(
    video_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    path = get_artifact_path(db, video_id, "accessible_video")
    if not path:
        raise HTTPException(status_code=404, detail="Accessible video not ready or not found.")
    return FileResponse(path=path, media_type="video/mp4", filename=f"seeless_{video_id}.mp4")


@router.get("/{video_id}/stream/video")
async def stream_video(
    video_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    path = get_artifact_path(db, video_id, "accessible_video")
    if not path:
        raise HTTPException(status_code=404, detail="Video stream not available.")
    return FileResponse(path=path, media_type="video/mp4")


@router.get("/{video_id}/stream/audio")
async def stream_audio_description(
    video_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    path = get_artifact_path(db, video_id, "audio_description")
    if not path:
        raise HTTPException(status_code=404, detail="Audio description track not found.")
    return FileResponse(path=path, media_type="audio/wav", filename=f"seeless_ad_{video_id}.wav")


@router.get("/{video_id}/stream/transcript")
async def stream_transcript(
    video_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    path = get_artifact_path(db, video_id, "transcript")
    if not path:
        raise HTTPException(status_code=404, detail="Transcript not found.")
    return FileResponse(path=path, media_type="application/json", filename=f"seeless_transcript_{video_id}.json")
