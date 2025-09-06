"""
Typed repository helpers for common DB operations.

These helpers wrap SQLAlchemy ORM operations with clear, typed functions
to simplify usage across services and CLIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import Select, and_, desc, func, select, exists
from sqlalchemy.orm import Session

from .models import (
    Base,
    Channel,
    Recording,
    Segment,
    Transcript,
    SegmentEmbedding,
)


# -------------------- Channels --------------------

def upsert_channel(
    db: Session,
    *,
    channel_id: str,
    name: str,
    url: str,
    headers: Optional[dict] = None,
    active: bool = True,
    description: Optional[str] = None,
) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        channel = Channel(
            id=channel_id,
            name=name,
            url=url,
            headers=headers or {},
            active=active,
            description=description,
        )
        db.add(channel)
    else:
        channel.name = name
        channel.url = url
        channel.headers = headers or {}
        channel.active = active
        channel.description = description
        db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def get_channel(db: Session, channel_id: str) -> Optional[Channel]:
    return db.get(Channel, channel_id)


def list_channels(db: Session, *, active_only: bool = False, limit: int = 100, offset: int = 0) -> List[Channel]:
    stmt: Select = select(Channel)
    if active_only:
        stmt = stmt.where(Channel.active.is_(True))
    stmt = stmt.order_by(Channel.created_at.asc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


# -------------------- Recordings --------------------

def create_recording(
    db: Session,
    *,
    channel_id: str,
    started_at: Optional[datetime] = None,
    status: str = "running",
    error_message: Optional[str] = None,
) -> Recording:
    if started_at is None:
        started_at = datetime.now(timezone.utc)
    rec = Recording(
        id=uuid4(),
        channel_id=channel_id,
        started_at=started_at,
        status=status,
        error_message=error_message,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def complete_recording(
    db: Session,
    *,
    recording_id: UUID,
    started_at: datetime,
    ended_at: Optional[datetime] = None,
    status: str = "completed",
) -> Optional[Recording]:
    rec = db.get(Recording, (recording_id, started_at))
    if rec is None:
        return None
    rec.ended_at = ended_at or datetime.now(timezone.utc)
    rec.status = status
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def list_recent_recordings(
    db: Session,
    *,
    channel_id: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
) -> List[Recording]:
    stmt: Select = select(Recording)
    if channel_id:
        stmt = stmt.where(Recording.channel_id == channel_id)
    if since:
        stmt = stmt.where(Recording.started_at >= since)
    if status:
        stmt = stmt.where(Recording.status == status)
    stmt = stmt.order_by(desc(Recording.started_at)).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


# -------------------- Segments --------------------

def upsert_segment(
    db: Session,
    *,
    segment_id: UUID,
    recording_id: UUID,
    channel_id: str,
    started_at: datetime,
    ended_at: datetime,
    audio_path: Optional[str],
    video_path: Optional[str],
    file_size_bytes: Optional[int],
    status: str = "completed",
) -> Segment:
    seg = db.get(Segment, (segment_id, started_at))
    if seg is None:
        seg = Segment(
            id=segment_id,
            recording_id=recording_id,
            channel_id=channel_id,
            started_at=started_at,
            ended_at=ended_at,
            audio_path=audio_path,
            video_path=video_path,
            file_size_bytes=file_size_bytes,
            status=status,
        )
        db.add(seg)
    else:
        # Update only if provided
        if audio_path and not seg.audio_path:
            seg.audio_path = audio_path
        if video_path and not seg.video_path:
            seg.video_path = video_path
        if file_size_bytes and (not seg.file_size_bytes or file_size_bytes > seg.file_size_bytes):
            seg.file_size_bytes = file_size_bytes
        seg.ended_at = ended_at
        seg.status = status
        db.add(seg)
    db.commit()
    db.refresh(seg)
    return seg


def list_segments(
    db: Session,
    *,
    channel_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 200,
    offset: int = 0,
    status: Optional[str] = None,
) -> List[Segment]:
    stmt: Select = select(Segment)
    if channel_id:
        stmt = stmt.where(Segment.channel_id == channel_id)
    if start:
        stmt = stmt.where(Segment.started_at >= start)
    if end:
        stmt = stmt.where(Segment.started_at < end)
    if status:
        stmt = stmt.where(Segment.status == status)
    stmt = stmt.order_by(desc(Segment.started_at)).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


# -------------------- Transcripts --------------------

def upsert_transcript(
    db: Session,
    *,
    segment_id: UUID,
    segment_started_at: datetime,
    text: str,
    language: str = "ar",
    confidence: Optional[float] = None,
    model_name: str = "unknown",
    model_version: Optional[str] = None,
    words: Optional[list] = None,
    processing_time_ms: Optional[int] = None,
    engine_time_ms: Optional[int] = None,
) -> Transcript:
    tr = db.get(Transcript, (segment_id, segment_started_at))
    if tr is None:
        tr = Transcript(
            segment_id=segment_id,
            segment_started_at=segment_started_at,
            language=language,
            text=text,
            words=words,
            confidence=confidence,
            model_name=model_name,
            model_version=model_version,
            processing_time_ms=processing_time_ms,
            engine_time_ms=engine_time_ms,
        )
        db.add(tr)
    else:
        tr.text = text
        tr.language = language
        tr.confidence = confidence
        tr.model_name = model_name
        tr.model_version = model_version
        tr.words = words
        tr.processing_time_ms = processing_time_ms
        tr.engine_time_ms = engine_time_ms
        db.add(tr)
    db.commit()
    db.refresh(tr)
    return tr


def list_recent_transcripts(
    db: Session,
    *,
    channel_id: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Tuple[Segment, Transcript]]:
    # Join on composite keys via manual where conditions
    seg_stmt = select(Segment)
    if channel_id:
        seg_stmt = seg_stmt.where(Segment.channel_id == channel_id)
    if since:
        seg_stmt = seg_stmt.where(Segment.started_at >= since)
    seg_stmt = seg_stmt.order_by(desc(Segment.started_at)).offset(offset).limit(limit)
    segments = list(db.execute(seg_stmt).scalars().all())
    results: List[Tuple[Segment, Transcript]] = []
    for seg in segments:
        tr = db.get(Transcript, (seg.id, seg.started_at))
        if tr is not None:
            results.append((seg, tr))
    return results


# -------------------- Embeddings (pgvector) --------------------

def upsert_embedding(
    db: Session,
    *,
    segment_id: UUID,
    segment_started_at: datetime,
    model_name: str,
    vector: Optional[list[float]],
) -> SegmentEmbedding:
    emb = db.get(SegmentEmbedding, (segment_id, segment_started_at))
    if emb is None:
        emb = SegmentEmbedding(
            segment_id=segment_id,
            segment_started_at=segment_started_at,
            model_name=model_name,
            vector=vector,
        )
        db.add(emb)
    else:
        emb.model_name = model_name
        emb.vector = vector
        db.add(emb)
    db.commit()
    db.refresh(emb)
    return emb


def semantic_search_segments_by_vector(
    db: Session,
    *,
    query_vector: list[float],
    top_k: int = 5,
    model_name: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> List[Tuple[Segment, float]]:
    """Return top-k segments most similar to the query vector (L2 distance).

    Filters by embedding model and/or channel when provided.
    """
    # Build distance expression using pgvector comparator
    distance = SegmentEmbedding.vector.l2_distance(query_vector)  # type: ignore[attr-defined]

    stmt: Select = select(Segment, distance.label("distance")).where(
        SegmentEmbedding.segment_id == Segment.id,
        SegmentEmbedding.segment_started_at == Segment.started_at,
    )
    if model_name:
        stmt = stmt.where(SegmentEmbedding.model_name == model_name)
    if channel_id:
        stmt = stmt.where(Segment.channel_id == channel_id)
    stmt = stmt.order_by(distance.asc()).limit(top_k)

    rows = list(db.execute(stmt).all())
    # rows are tuples: (Segment, distance)
    return [(row[0], float(row[1])) for row in rows]


# -------------------- Helpers for ASR pipeline --------------------

def list_segments_missing_transcripts(
    db: Session,
    *,
    channel_id: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 200,
) -> List[Segment]:
    """List recent completed segments that have audio and no transcript yet.

    Results ordered by newest first.
    """
    tr_exists = (
        select(Transcript.segment_id)
        .where(
            Transcript.segment_id == Segment.id,
            Transcript.segment_started_at == Segment.started_at,
        )
        .limit(1)
    )
    stmt: Select = select(Segment).where(
        Segment.audio_path.is_not(None),
        Segment.status == "completed",
        ~exists(tr_exists),
    )
    if channel_id:
        stmt = stmt.where(Segment.channel_id == channel_id)
    if since:
        stmt = stmt.where(Segment.started_at >= since)
    stmt = stmt.order_by(desc(Segment.started_at)).limit(limit)
    return list(db.execute(stmt).scalars().all())

