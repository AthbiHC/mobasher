"""
SQLAlchemy models for Mobasher database.

These models correspond to the TimescaleDB schema with proper relationships
and type annotations for the live TV analysis system.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, BigInteger, Real, DateTime,
    JSON, ARRAY, ForeignKey, CheckConstraint, Index, text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, VECTOR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

Base = declarative_base()


class Channel(Base):
    """TV channel configuration and metadata."""
    
    __tablename__ = "channels"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String, nullable=False)
    headers: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    recordings: Mapped[List["Recording"]] = relationship("Recording", back_populates="channel")
    segments: Mapped[List["Segment"]] = relationship("Segment", back_populates="channel")
    visual_events: Mapped[List["VisualEvent"]] = relationship("VisualEvent", back_populates="channel")
    system_metrics: Mapped[List["SystemMetric"]] = relationship("SystemMetric", back_populates="channel")


class Recording(Base):
    """Recording session for a TV channel (TimescaleDB hypertable)."""
    
    __tablename__ = "recordings"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), default=uuid4)
    channel_id: Mapped[str] = mapped_column(String, ForeignKey("channels.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String, 
        CheckConstraint("status IN ('running', 'completed', 'failed', 'stopped')"),
        default="running"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Composite primary key for TimescaleDB
    __table_args__ = (
        {"primary_key": [id, started_at]},
        Index("idx_recordings_channel_time", "channel_id", "started_at"),
    )
    
    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="recordings")
    segments: Mapped[List["Segment"]] = relationship("Segment", back_populates="recording")


class Segment(Base):
    """Audio/video segment from recording (TimescaleDB hypertable)."""
    
    __tablename__ = "segments"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), default=uuid4)
    recording_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    channel_id: Mapped[str] = mapped_column(String, ForeignKey("channels.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # duration_seconds is computed in database as GENERATED column
    audio_path: Mapped[str] = mapped_column(String, nullable=False)
    video_path: Mapped[Optional[str]] = mapped_column(String)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(
        String,
        CheckConstraint("status IN ('created', 'processing', 'completed', 'failed')"),
        default="created"
    )
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Composite primary key for TimescaleDB
    __table_args__ = (
        {"primary_key": [id, started_at]},
        Index("idx_segments_channel_time", "channel_id", "started_at"),
        Index("idx_segments_recording", "recording_id", "started_at"),
    )
    
    # Relationships (no FK to recordings due to TimescaleDB limitation)
    channel: Mapped["Channel"] = relationship("Channel", back_populates="segments")
    recording: Mapped["Recording"] = relationship("Recording", back_populates="segments")
    transcript: Mapped[Optional["Transcript"]] = relationship("Transcript", back_populates="segment")
    embedding: Mapped[Optional["SegmentEmbedding"]] = relationship("SegmentEmbedding", back_populates="segment")
    visual_events: Mapped[List["VisualEvent"]] = relationship("VisualEvent", back_populates="segment")


class Transcript(Base):
    """ASR transcript for segment."""
    
    __tablename__ = "transcripts"
    
    segment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    segment_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    language: Mapped[str] = mapped_column(String, default="ar")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    words: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON)  # Word-level timestamps
    confidence: Mapped[Optional[float]] = mapped_column(Real)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        {"primary_key": [segment_id, segment_started_at]},
        Index("idx_transcripts_language", "language"),
        Index("idx_transcripts_segment", "segment_id", "segment_started_at"),
        # Full-text search index (created in database)
        Index("idx_transcripts_text_search", text, postgresql_using="gin", 
              postgresql_ops={"text": "gin_trgm_ops"}),
    )
    
    # Relationships (no FK due to TimescaleDB limitation)
    segment: Mapped["Segment"] = relationship("Segment", back_populates="transcript")


class SegmentEmbedding(Base):
    """Vector embeddings for segment content."""
    
    __tablename__ = "segment_embeddings"
    
    segment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    segment_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    vector: Mapped[Optional[List[float]]] = mapped_column(VECTOR(384))  # Adjust dimension as needed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        {"primary_key": [segment_id, segment_started_at]},
        Index("idx_embeddings_segment", "segment_id", "segment_started_at"),
        # Vector similarity index (created after data insertion)
        # Index("idx_embeddings_vector", "vector", postgresql_using="ivfflat"),
    )
    
    # Relationships (no FK due to TimescaleDB limitation)
    segment: Mapped["Segment"] = relationship("Segment", back_populates="embedding")


class VisualEvent(Base):
    """Computer vision analysis results (TimescaleDB hypertable)."""
    
    __tablename__ = "visual_events"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), default=uuid4)
    segment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    segment_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel_id: Mapped[str] = mapped_column(String, ForeignKey("channels.id"), nullable=False)
    timestamp_offset: Mapped[float] = mapped_column(Real, nullable=False)  # Seconds from segment start
    event_type: Mapped[str] = mapped_column(
        String,
        CheckConstraint("event_type IN ('object', 'face', 'ocr', 'logo', 'scene_change')"),
        nullable=False
    )
    bbox: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer))  # [x, y, width, height]
    confidence: Mapped[Optional[float]] = mapped_column(Real)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # Event-specific data
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        {"primary_key": [id, created_at]},
        Index("idx_visual_events_segment", "segment_id", "segment_started_at"),
        Index("idx_visual_events_type", "event_type"),
    )
    
    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="visual_events")
    segment: Mapped["Segment"] = relationship("Segment", back_populates="visual_events")


class SystemMetric(Base):
    """System monitoring metrics (TimescaleDB hypertable)."""
    
    __tablename__ = "system_metrics"
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    metric_value: Mapped[float] = mapped_column(Real, nullable=False)
    tags: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    channel_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("channels.id"))
    
    __table_args__ = (
        {"primary_key": [id, timestamp]},
        Index("idx_system_metrics_name", "metric_name", "timestamp"),
    )
    
    # Relationships
    channel: Mapped[Optional["Channel"]] = relationship("Channel", back_populates="system_metrics")


# Database views (read-only, defined in schema.sql)
class RecentSegmentsView(Base):
    """View for recent segments with transcript data."""
    
    __tablename__ = "recent_segments"
    __table_args__ = {"info": {"is_view": True}}
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String)
    channel_name: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Real)
    status: Mapped[str] = mapped_column(String)
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    transcript_confidence: Mapped[Optional[float]] = mapped_column(Real)


class ChannelStatsView(Base):
    """View for channel statistics."""
    
    __tablename__ = "channel_stats"
    __table_args__ = {"info": {"is_view": True}}
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    total_segments: Mapped[int] = mapped_column(Integer)
    transcribed_segments: Mapped[int] = mapped_column(Integer)
    avg_confidence: Mapped[Optional[float]] = mapped_column(Real)
    last_segment_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
