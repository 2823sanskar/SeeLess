from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class VideoUploadResponse(BaseModel):
    video_id: str
    job_id: str
    status: str
    filename: str

class VideoDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    duration: Optional[float] = None
    status: str
    created_at: datetime
    updated_at: datetime

class ProcessingStatusResponse(BaseModel):
    video_id: str
    status: str
    current_step: str
    progress: int
    error: Optional[str] = None

class SpeechSegmentSchema(BaseModel):
    start: float
    end: float
    text: Optional[str] = None

class VisualEventSchema(BaseModel):
    start: float
    end: float
    subject: Optional[str] = None
    action: Optional[str] = None
    importance: float = 0.5
    confidence: float = 1.0

class DescriptionSchema(BaseModel):
    id: Optional[str] = None
    start: float
    end: float
    text: str
    priority: float = 0.5
    status: str = "PROPOSED"

class ScheduledDescriptionSchema(BaseModel):
    description_id: str
    text: str
    start: float
    end: float
    status: str
    reason: Optional[str] = None

class VideoResultResponse(BaseModel):
    video_id: str
    status: str
    final_video_url: Optional[str] = None
    audio_description_url: Optional[str] = None
    transcript_url: Optional[str] = None
    descriptions: List[DescriptionSchema] = []
    speech_segments: List[SpeechSegmentSchema] = []

class ErrorResponse(BaseModel):
    detail: str
