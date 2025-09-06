from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from mobasher.asr.enqueue import enqueue_missing


async def run_scheduler(
    *,
    channel_id: Optional[str] = None,
    interval_seconds: int = 30,
    lookback_minutes: int = 10,
    max_interval_seconds: int = 300,
) -> None:
    """Periodic enqueue with exponential backoff and jitter on errors."""
    current_interval = max(10, interval_seconds)
    while True:
        since = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        try:
            enq = enqueue_missing(channel_id=channel_id, since=since, limit=200)
            print(f"asr-scheduler: enqueued={enq}")
            # success: reset interval to base
            current_interval = max(10, interval_seconds)
        except Exception as e:
            print(f"asr-scheduler error: {e}")
            # backoff: double up to max, add jitter 0-20%
            current_interval = min(max_interval_seconds, int(current_interval * 2))
        # add small jitter each loop to avoid thundering herd
        jitter = random.uniform(-0.2, 0.2)
        sleep_for = max(5, int(current_interval * (1 + jitter)))
        await asyncio.sleep(sleep_for)


def run_scheduler_blocking(
    *,
    channel_id: Optional[str] = None,
    interval_seconds: int = 30,
    lookback_minutes: int = 10,
    max_interval_seconds: int = 300,
) -> None:
    asyncio.run(
        run_scheduler(
            channel_id=channel_id,
            interval_seconds=interval_seconds,
            lookback_minutes=lookback_minutes,
            max_interval_seconds=max_interval_seconds,
        )
    )


