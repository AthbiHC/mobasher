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


