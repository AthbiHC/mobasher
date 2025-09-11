from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import redis  # type: ignore

from mobasher.storage.db import get_session, init_engine
from mobasher.storage.repositories import list_segments_missing_transcripts
from mobasher.asr.worker import transcribe_segment


_REDIS: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _REDIS
    if _REDIS is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _REDIS = redis.from_url(url)
    return _REDIS


def enqueue_missing(
    channel_id: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 200,
    dedupe_ttl_seconds: int = 3600,
) -> int:
    """Enqueue recent segments missing transcripts.

    Dedupe using Redis keys with TTL to avoid repeat enqueues for the same segment.
    """
    init_engine()
    r = _get_redis()
    count = 0
    with next(get_session()) as db:  # type: ignore
        segs = list_segments_missing_transcripts(db, channel_id=channel_id, since=since, limit=limit)
        for seg in segs:
            key = f"asr:queued:{seg.id}:{seg.started_at.isoformat()}"
            # set NX: only if not exists
            ok = r.set(key, "1", nx=True, ex=dedupe_ttl_seconds)
            if not ok:
                continue
            try:
                # mark queued
                from mobasher.storage.models import Segment as _Seg
                s = db.get(_Seg, (seg.id, seg.started_at))
                if s is not None:
                    s.asr_status = "queued"
                    db.add(s)
                    db.commit()
            except Exception:
                pass
            transcribe_segment.delay(str(seg.id), seg.started_at.isoformat())
            count += 1
    return count


