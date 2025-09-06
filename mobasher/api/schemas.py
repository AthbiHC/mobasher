from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class ChannelOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    url: str
    headers: Dict[str, Any] = Field(default_factory=dict)
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChannelIn(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    url: str
    headers: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class RecordingOut(BaseModel):
    id: UUID
    channel_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SegmentOut(BaseModel):
    id: UUID
    recording_id: UUID
    channel_id: str
    started_at: datetime
    ended_at: datetime
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    status: str

    class Config:
        from_attributes = True


class PageMeta(BaseModel):
    limit: int
    offset: int
    next_offset: Optional[int] = None


class PaginatedChannels(BaseModel):
    items: list[ChannelOut]
    meta: PageMeta


class PaginatedRecordings(BaseModel):
    items: list[RecordingOut]
    meta: PageMeta


class PaginatedSegments(BaseModel):
    items: list[SegmentOut]
    meta: PageMeta


class TranscriptOut(BaseModel):
    segment_id: UUID
    segment_started_at: datetime
    language: str
    text: str
    confidence: Optional[float] = None
    model_name: str

    class Config:
        from_attributes = True


class SegmentWithTranscript(BaseModel):
    segment: SegmentOut
    transcript: TranscriptOut


class PaginatedTranscripts(BaseModel):
    items: list[SegmentWithTranscript]
    meta: PageMeta


# -------- Visual Events --------

class VisualEventOut(BaseModel):
    id: UUID
    segment_id: UUID
    segment_started_at: datetime
    channel_id: str
    timestamp_offset: float
    event_type: str
    bbox: Optional[List[int]] = None
    confidence: Optional[float] = None
    data: Dict[str, Any]
    created_at: datetime
    video_filename: Optional[str] = None
    screenshot_path: Optional[str] = None
    frame_timestamp_ms: Optional[int] = None

    class Config:
        from_attributes = True


class PaginatedVisualEvents(BaseModel):
    items: list[VisualEventOut]
    meta: PageMeta

