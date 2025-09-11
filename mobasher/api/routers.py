from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .schemas import (
    ChannelIn,
    ChannelOut,
    RecordingOut,
    SegmentOut,
    PaginatedChannels,
    PaginatedRecordings,
    PaginatedSegments,
    PageMeta,
    PaginatedTranscripts,
    SegmentWithTranscript,
    PaginatedVisualEvents,
    VisualEventOut,
    PaginatedScreenshots,
    ScreenshotOut,
)
from .deps import get_db
from mobasher.storage.repositories import (
    get_channel,
    list_channels,
    upsert_channel,
    list_recent_recordings,
    list_segments,
    list_recent_transcripts,
)
from mobasher.storage.models import VisualEvent
from mobasher.storage.models import Screenshot


router = APIRouter()


@router.get("/health", tags=["system"]) 
def health() -> dict:
    return {"status": "ok"}


@router.get("/channels", response_model=PaginatedChannels, tags=["channels"]) 
def api_list_channels(
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedChannels:
    items = list_channels(db, active_only=active_only, limit=limit, offset=offset)
    next_offset = offset + len(items) if len(items) == limit else None
    return PaginatedChannels(items=items, meta=PageMeta(limit=limit, offset=offset, next_offset=next_offset))


@router.get("/channels/{channel_id}", response_model=ChannelOut, tags=["channels"])
def api_get_channel(channel_id: str, db: Session = Depends(get_db)) -> ChannelOut:
    ch = get_channel(db, channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ch


@router.post("/channels", response_model=ChannelOut, tags=["channels"])
def api_upsert_channel(payload: ChannelIn, db: Session = Depends(get_db)) -> ChannelOut:
    ch = upsert_channel(
        db,
        channel_id=payload.id,
        name=payload.name,
        url=payload.url,
        headers=payload.headers,
        active=payload.active,
        description=payload.description,
    )
    return ch


@router.get("/recordings", response_model=PaginatedRecordings, tags=["recordings"]) 
def api_list_recordings(
    channel_id: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, pattern="^(running|completed|failed|stopped)$"),
    db: Session = Depends(get_db),
) -> PaginatedRecordings:
    items = list_recent_recordings(db, channel_id=channel_id, since=since, limit=limit, offset=offset, status=status)
    next_offset = offset + len(items) if len(items) == limit else None
    return PaginatedRecordings(items=items, meta=PageMeta(limit=limit, offset=offset, next_offset=next_offset))


@router.get("/segments", response_model=PaginatedSegments, tags=["segments"]) 
def api_list_segments(
    channel_id: Optional[str] = Query(None),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, pattern="^(created|processing|completed|failed)$"),
    db: Session = Depends(get_db),
) -> PaginatedSegments:
    items = list_segments(db, channel_id=channel_id, start=start, end=end, limit=limit, offset=offset, status=status)
    next_offset = offset + len(items) if len(items) == limit else None
    return PaginatedSegments(items=items, meta=PageMeta(limit=limit, offset=offset, next_offset=next_offset))


@router.get("/transcripts", response_model=PaginatedTranscripts, tags=["transcripts"]) 
def api_list_transcripts(
    channel_id: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedTranscripts:
    pairs = list_recent_transcripts(db, channel_id=channel_id, since=since, limit=limit, offset=offset)
    items = [SegmentWithTranscript(segment=p[0], transcript=p[1]) for p in pairs]
    next_offset = offset + len(items) if len(items) == limit else None
    return PaginatedTranscripts(items=items, meta=PageMeta(limit=limit, offset=offset, next_offset=next_offset))

@router.get("/visual-events", response_model=PaginatedVisualEvents, tags=["vision"]) 
def api_list_visual_events(
    channel_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, pattern="^(ocr|object|face|logo|scene_change)$"),
    region: Optional[str] = Query(None, description="Filter by data.region"),
    q: Optional[str] = Query(None, description="Contains search in data.text (simple ILIKE)"),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    min_conf: Optional[float] = Query(None, ge=0, le=1),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedVisualEvents:
    # Build query with simple filters; for performance, consider indexes on created_at/channel
    query = db.query(VisualEvent)
    if channel_id:
        query = query.filter(VisualEvent.channel_id == channel_id)
    if event_type:
        query = query.filter(VisualEvent.event_type == event_type)
    if min_conf is not None:
        query = query.filter(VisualEvent.confidence >= min_conf)
    if since:
        query = query.filter(VisualEvent.created_at >= since)
    if until:
        query = query.filter(VisualEvent.created_at < until)
    if region:
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB
        query = query.filter(cast(VisualEvent.data, JSONB)["region"].astext == region)
    if q:
        from sqlalchemy import func
        query = query.filter(func.lower((VisualEvent.data["text"].astext))).like(f"%{q.lower()}%")

    items = (
        query.order_by(VisualEvent.created_at.desc()).offset(offset).limit(limit).all()
    )
    next_offset = offset + len(items) if len(items) == limit else None
    return PaginatedVisualEvents(items=items, meta=PageMeta(limit=limit, offset=offset, next_offset=next_offset))


@router.get("/screenshots", response_model=PaginatedScreenshots, tags=["vision"]) 
def api_list_screenshots(
    channel_id: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    limit: int = Query(24, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> PaginatedScreenshots:
    query = db.query(Screenshot)
    if channel_id:
        query = query.filter(Screenshot.channel_id == channel_id)
    if since:
        query = query.filter(Screenshot.created_at >= since)
    items = (
        query.order_by(Screenshot.created_at.desc()).offset(offset).limit(limit).all()
    )
    next_offset = offset + len(items) if len(items) == limit else None
    return PaginatedScreenshots(items=items, meta=PageMeta(limit=limit, offset=offset, next_offset=next_offset))



