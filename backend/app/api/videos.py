"""
api/videos.py
-------------
REST endpoints for video upload, processing, status, result and download.
Delegates DB logic to video_service; delegates processing to Celery / BackgroundTasks.
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Description, ProcessingArtifact, SpeechSegment, Video
from app.schemas import (
    BatchUploadItemSchema,
    BatchVideoUploadResponse,
    BulkExportRequest,
    DescriptionSchema,
    ProcessingStatusResponse,
    SpeechSegmentSchema,
    VideoListResponse,
    VideoResultResponse,
    VideoUploadResponse,
)
from app.services.extraction_service import validate_video
from app.services.video_service import (
    create_bulk_export_zip,
    create_pending_job,
    create_queued_job,
    delete_video_and_storage,
    generate_srt_content,
    generate_vtt_content,
    get_artifact_path,
    get_latest_job,
    get_video_or_404,
    list_videos,
    mark_job_queued,
)
from app.utils.file_utils import init_video_storage, sanitize_filename
from app.utils.logging_utils import logger
from app.workers.tasks import (
    USING_CELERY,
    execute_batch_pipeline,
    execute_video_pipeline,
    process_batch_task,
    process_video_task,
)

router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.get("", response_model=VideoListResponse)
async def get_all_videos(
    search: Optional[str] = Query(None, description="Search by filename"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field (created_at, duration, original_filename)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_db),
) -> VideoListResponse:
    """List, search, and filter workspace video library."""
    return list_videos(
        db=db,
        search=search,
        status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


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
    from app.workers.tasks import process_video_task, USING_CELERY, execute_video_pipeline

    if USING_CELERY:
        # Dispatch to Celery if available
        process_video_task.delay(video_id)
        celery_dispatched = True
        logger.info(f"Video {video_id} dispatched to Celery.")
    else:
        # Fallback to FastAPI BackgroundTasks
        background_tasks.add_task(execute_video_pipeline, video_id)
        celery_dispatched = False
        logger.info(f"Celery unavailable; processing video {video_id} via BackgroundTasks.")

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


@router.post("/batch-upload", response_model=BatchVideoUploadResponse, status_code=201)
async def upload_batch_videos(
    files: List[UploadFile] = File(...),
    auto_process: bool = Form(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
) -> BatchVideoUploadResponse:
    """Accept multiple MP4 videos for batch ingestion and optional concurrent queuing."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    batch_id = str(uuid.uuid4())
    uploaded_items: List[BatchUploadItemSchema] = []
    video_ids_to_process: List[str] = []

    for file in files:
        if Path(file.filename or "").suffix.lower() != ".mp4":
            continue

        safe_name = sanitize_filename(file.filename or "upload.mp4")
        new_video = Video(
            batch_id=batch_id,
            original_filename=safe_name,
            original_file_path="",
            status="UPLOADED",
        )
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
            logger.error(f"Failed to save file '{safe_name}' in batch: {exc}")
            continue

        new_video.original_file_path = str(dest_path.resolve())

        try:
            meta = validate_video(new_video.original_file_path)
            new_video.duration = meta["duration"]
            db.commit()
        except Exception as exc:
            logger.warning(f"Batch validation warning for '{safe_name}': {exc}")

        job = create_pending_job(db, new_video.id)

        uploaded_items.append(
            BatchUploadItemSchema(
                video_id=new_video.id,
                job_id=job.id,
                filename=safe_name,
                status="UPLOADED",
                duration=new_video.duration,
            )
        )
        video_ids_to_process.append(new_video.id)

    if not uploaded_items:
        raise HTTPException(status_code=400, detail="No valid MP4 video files were uploaded.")

    if auto_process and video_ids_to_process:
        for vid in video_ids_to_process:
            job = get_latest_job(db, vid)
            if job:
                mark_job_queued(db, job)

        if USING_CELERY:
            process_batch_task.delay(video_ids_to_process)
            logger.info(f"Queued batch of {len(video_ids_to_process)} videos via Celery.")
        else:
            background_tasks.add_task(execute_batch_pipeline, video_ids_to_process)
            logger.info(f"Queued batch of {len(video_ids_to_process)} videos via BackgroundTasks.")

    return BatchVideoUploadResponse(
        batch_id=batch_id,
        total_uploaded=len(uploaded_items),
        videos=uploaded_items,
    )


@router.get("/{video_id}/export/vtt")
async def export_webvtt_subtitles(
    video_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Generate and export standard WebVTT subtitles."""
    video = get_video_or_404(db, video_id)
    descriptions = db.query(Description).filter(Description.video_id == video_id).all()
    speech_segments = db.query(SpeechSegment).filter(SpeechSegment.video_id == video_id).all()

    vtt_text = generate_vtt_content(descriptions, speech_segments)
    clean_name = video.original_filename.rsplit(".", 1)[0]
    return Response(
        content=vtt_text,
        media_type="text/vtt",
        headers={"Content-Disposition": f'attachment; filename="{clean_name}_descriptions.vtt"'},
    )


@router.get("/{video_id}/export/srt")
async def export_srt_subtitles(
    video_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Generate and export standard SubRip (SRT) subtitles."""
    video = get_video_or_404(db, video_id)
    descriptions = db.query(Description).filter(Description.video_id == video_id).all()
    speech_segments = db.query(SpeechSegment).filter(SpeechSegment.video_id == video_id).all()

    srt_text = generate_srt_content(descriptions, speech_segments)
    clean_name = video.original_filename.rsplit(".", 1)[0]
    return Response(
        content=srt_text,
        media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{clean_name}_descriptions.srt"'},
    )


@router.post("/bulk-export")
async def bulk_export_assets(
    request: BulkExportRequest,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Package requested accessible assets across multiple videos into a downloadable zip archive."""
    if not request.video_ids:
        raise HTTPException(status_code=400, detail="No video IDs provided.")

    zip_path, file_count = create_bulk_export_zip(
        db=db,
        video_ids=request.video_ids,
        export_types=request.export_types,
    )

    if file_count == 0:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(status_code=404, detail="No requested assets found for selected videos.")

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename="seeless_bulk_export.zip",
    )


@router.delete("/{video_id}", status_code=204)
async def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete video, associated database records, and all stored assets."""
    delete_video_and_storage(db, video_id)
