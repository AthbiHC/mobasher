from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from mobasher.storage.db import get_session, init_engine
from mobasher.storage.models import Segment, Transcript
from mobasher.nlp.worker import entities_for_transcript, alerts_for_transcript


async def run_scheduler(*, interval_seconds: int = 30, lookback_minutes: int = 10, channel_id: Optional[str] = None) -> None:
    init_engine()
    while True:
        since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        try:
            with next(get_session()) as db:  # type: ignore
                q = db.query(Segment).filter(Segment.started_at >= since)
                if channel_id:
                    q = q.filter(Segment.channel_id == channel_id)
                segs = q.order_by(Segment.started_at.desc()).limit(200).all()
                enq = 0
                for seg in segs:
                    tr = db.get(Transcript, (seg.id, seg.started_at))
                    if tr is None:
                        continue
                    entities_for_transcript.delay(str(seg.id), seg.started_at.isoformat())
                    alerts_for_transcript.delay(str(seg.id), seg.started_at.isoformat())
                    enq += 1
                print(f"nlp-scheduler: enqueued={enq}")
        except Exception as e:
            print(f"nlp-scheduler error: {e}")
        await asyncio.sleep(max(5, interval_seconds))


def run_scheduler_blocking(*, interval_seconds: int = 30, lookback_minutes: int = 10, channel_id: Optional[str] = None) -> None:
    asyncio.run(run_scheduler(interval_seconds=interval_seconds, lookback_minutes=lookback_minutes, channel_id=channel_id))


