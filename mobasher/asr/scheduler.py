from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from mobasher.asr.enqueue import enqueue_missing


async def run_scheduler(
    *,
    channel_id: Optional[str] = None,
    interval_seconds: int = 30,
    lookback_minutes: int = 10,
) -> None:
    while True:
        since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        try:
            enq = enqueue_missing(channel_id=channel_id, since=since, limit=200)
            print(f"asr-scheduler: enqueued={enq}")
        except Exception as e:
            print(f"asr-scheduler error: {e}")
        await asyncio.sleep(max(10, interval_seconds))


def run_scheduler_blocking(
    *,
    channel_id: Optional[str] = None,
    interval_seconds: int = 30,
    lookback_minutes: int = 10,
) -> None:
    asyncio.run(run_scheduler(channel_id=channel_id, interval_seconds=interval_seconds, lookback_minutes=lookback_minutes))


