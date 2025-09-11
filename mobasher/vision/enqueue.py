from __future__ import annotations

from datetime import datetime
from typing import Optional

from mobasher.storage.db import get_session, init_engine
from mobasher.storage.models import Segment, Transcript
from mobasher.vision.worker import ocr_segment, objects_segment, faces_segment


def enqueue_vision_for_asr_processed(limit: int = 20) -> int:
    """Enqueue OCR tasks for segments that have video and an existing transcript.

    Focuses the first N by start time.
    """
    init_engine()
    count = 0
    with next(get_session()) as db:  # type: ignore
        # Join-like query: segment with video and transcript present
        segs = (
            db.query(Segment)
            .filter(Segment.video_path != None)
            .order_by(Segment.started_at.asc())
            .limit(limit * 3)
            .all()
        )
        for seg in segs:
            tr = db.get(Transcript, (seg.id, seg.started_at))
            if tr is None:
                continue
            ocr_segment.delay(str(seg.id), seg.started_at.isoformat())
            objects_segment.delay(str(seg.id), seg.started_at.isoformat())
            faces_segment.delay(str(seg.id), seg.started_at.isoformat())
            count += 1
            if count >= limit:
                break
    return count


def enqueue_screenshots_for_recent(limit: int = 20) -> int:
    """Enqueue screenshots for recent segments that have video (no transcript requirement)."""
    from mobasher.vision.worker import screenshots_segment
    init_engine()
    count = 0
    with next(get_session()) as db:  # type: ignore
        segs = (
            db.query(Segment)
            .filter(Segment.video_path != None)
            .order_by(Segment.started_at.desc())
            .limit(limit)
            .all()
        )
        for seg in segs:
            screenshots_segment.delay(str(seg.id), seg.started_at.isoformat())
            count += 1
    return count


