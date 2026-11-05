import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, Mapped
from app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    original_filename: Mapped[str] = Column(String, nullable=False)
    original_file_path: Mapped[str] = Column(String, nullable=False)
    duration: Mapped[Optional[float]] = Column(Float, nullable=True)
    status: Mapped[str] = Column(String, default="UPLOADED", nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    jobs = relationship("ProcessingJob", back_populates="video", cascade="all, delete-orphan")
    artifacts = relationship("ProcessingArtifact", back_populates="video", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="video", cascade="all, delete-orphan")
    speech_segments = relationship("SpeechSegment", back_populates="video", cascade="all, delete-orphan")
    visual_events = relationship("VisualEvent", back_populates="video", cascade="all, delete-orphan")
    descriptions = relationship("Description", back_populates="video", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Video id={self.id} filename={self.original_filename} status={self.status}>"

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = Column(String, ForeignKey("videos.id"), nullable=False, index=True)
    status: Mapped[str] = Column(String, default="PENDING", nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED
    current_step: Mapped[str] = Column(String, default="Initialized", nullable=False)
    progress: Mapped[int] = Column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)

    video = relationship("Video", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<ProcessingJob id={self.id} video_id={self.video_id} status={self.status} step={self.current_step}>"

class ProcessingArtifact(Base):
    __tablename__ = "processing_artifacts"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = Column(String, ForeignKey("videos.id"), nullable=False, index=True)
    artifact_type: Mapped[str] = Column(String, nullable=False)  # accessible_video, audio_description, transcript, metadata, frames
    file_path: Mapped[str] = Column(String, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    video = relationship("Video", back_populates="artifacts")

    def __repr__(self) -> str:
        return f"<ProcessingArtifact id={self.id} type={self.artifact_type} path={self.file_path}>"

class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = Column(String, ForeignKey("videos.id"), nullable=False, index=True)
    scene_number: Mapped[int] = Column(Integer, nullable=False)
    start_time: Mapped[float] = Column(Float, nullable=False)
    end_time: Mapped[float] = Column(Float, nullable=False)

    video = relationship("Video", back_populates="scenes")
    visual_events = relationship("VisualEvent", back_populates="scene", cascade="all, delete-orphan")
    descriptions = relationship("Description", back_populates="scene")

    def __repr__(self) -> str:
        return f"<Scene #{self.scene_number} [{self.start_time}s - {self.end_time}s]>"

class SpeechSegment(Base):
    __tablename__ = "speech_segments"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = Column(String, ForeignKey("videos.id"), nullable=False, index=True)
    start_time: Mapped[float] = Column(Float, nullable=False)
    end_time: Mapped[float] = Column(Float, nullable=False)
    transcript: Mapped[Optional[str]] = Column(Text, nullable=True)

    video = relationship("Video", back_populates="speech_segments")

    def __repr__(self) -> str:
        return f"<SpeechSegment [{self.start_time}s - {self.end_time}s] text='{self.transcript}'>"

class VisualEvent(Base):
    __tablename__ = "visual_events"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = Column(String, ForeignKey("videos.id"), nullable=False, index=True)
    scene_id: Mapped[Optional[str]] = Column(String, ForeignKey("scenes.id"), nullable=True, index=True)
    start_time: Mapped[float] = Column(Float, nullable=False)
    end_time: Mapped[float] = Column(Float, nullable=False)
    event_description: Mapped[str] = Column(Text, nullable=False)
    subject: Mapped[Optional[str]] = Column(String, nullable=True)
    importance: Mapped[float] = Column(Float, default=0.5)
    confidence: Mapped[float] = Column(Float, default=1.0)

    video = relationship("Video", back_populates="visual_events")
    scene = relationship("Scene", back_populates="visual_events")

    def __repr__(self) -> str:
        return f"<VisualEvent [{self.start_time}s - {self.end_time}s] subject={self.subject} desc={self.event_description}>"

class Description(Base):
    __tablename__ = "descriptions"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    video_id: Mapped[str] = Column(String, ForeignKey("videos.id"), nullable=False, index=True)
    scene_id: Mapped[Optional[str]] = Column(String, ForeignKey("scenes.id"), nullable=True, index=True)
    start_time: Mapped[float] = Column(Float, nullable=False)
    end_time: Mapped[float] = Column(Float, nullable=False)
    text: Mapped[str] = Column(Text, nullable=False)
    priority: Mapped[float] = Column(Float, default=0.5)
    status: Mapped[str] = Column(String, default="PROPOSED")  # PROPOSED, SCHEDULED, OMITTED

    video = relationship("Video", back_populates="descriptions")
    scene = relationship("Scene", back_populates="descriptions")
    narration_clips = relationship("NarrationClip", back_populates="description", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Description id={self.id} [{self.start_time}s - {self.end_time}s] status={self.status} text='{self.text}'>"

class NarrationClip(Base):
    __tablename__ = "narration_clips"

    id: Mapped[str] = Column(String, primary_key=True, default=generate_uuid)
    description_id: Mapped[str] = Column(String, ForeignKey("descriptions.id"), nullable=False, index=True)
    audio_file_path: Mapped[str] = Column(String, nullable=False)
    duration: Mapped[float] = Column(Float, nullable=False)
    scheduled_start: Mapped[float] = Column(Float, nullable=False)
    scheduled_end: Mapped[float] = Column(Float, nullable=False)
    status: Mapped[str] = Column(String, default="GENERATED")  # GENERATED, VALIDATED, FAILED

    description = relationship("Description", back_populates="narration_clips")

    def __repr__(self) -> str:
        return f"<NarrationClip id={self.id} desc_id={self.description_id} [{self.scheduled_start}s - {self.scheduled_end}s] dur={self.duration}s>"
