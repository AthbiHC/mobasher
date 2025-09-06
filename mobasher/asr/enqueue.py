from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from mobasher.storage.db import get_session, init_engine
from mobasher.storage.repositories import list_segments_missing_transcripts
from mobasher.asr.worker import transcribe_segment


def enqueue_missing(
    channel_id: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 200,
) -> int:
    init_engine()
    count = 0
    with next(get_session()) as db:  # type: ignore
        segs = list_segments_missing_transcripts(db, channel_id=channel_id, since=since, limit=limit)
        for seg in segs:
            transcribe_segment.delay(str(seg.id), seg.started_at.isoformat())
            count += 1
    return count


