from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from time import perf_counter

from celery import Celery
from pydantic_settings import BaseSettings


class VisionSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    ocr_fps: float = 3.0
    ocr_lang: str = "ar"  # EasyOCR language code


settings = VisionSettings()
app = Celery("mobasher_vision", broker=settings.redis_url, backend=settings.redis_url)


def _sample_timestamps(duration_s: float, fps: float) -> List[float]:
    if fps <= 0:
        return []
    step = 1.0 / fps
    t = 0.0
    out: List[float] = []
    while t < duration_s:
        out.append(round(t, 3))
        t += step
    return out


# Global OCR model cache
_OCR = None


def _get_ocr():
    global _OCR
    if _OCR is None:
        import easyocr  # type: ignore
        _OCR = easyocr.Reader([settings.ocr_lang], gpu=False, verbose=False)
    return _OCR


def _read_frame_at(video_path: str, ts_sec: float) -> Optional[Tuple[Any, int, int]]:
    import cv2  # type: ignore
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, ts_sec * 1000.0)
    ok, frame = cap.read()
    h, w = (frame.shape[0], frame.shape[1]) if ok and frame is not None else (0, 0)
    cap.release()
    if not ok or frame is None:
        return None
    return frame, w, h


@app.task(name="vision.ocr_segment", bind=True, max_retries=2, default_retry_delay=10)
def ocr_segment(self, segment_id: str, segment_started_at_iso: str) -> Dict[str, Any]:
    start = perf_counter()
    # Lazy imports to keep worker light
    from datetime import datetime
    from uuid import UUID
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.models import Segment, VisualEvent
    from mobasher.storage.repositories import upsert_segment  # if needed later
    import subprocess

    init_engine()
    with next(get_session()) as db:  # type: ignore
        seg = db.get(Segment, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
        if seg is None or not seg.video_path:
            raise self.retry(exc=RuntimeError("segment_missing_or_no_video"))

        # Probe duration via ffprobe
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nokey=1:noprint_wrappers=1', seg.video_path
            ], capture_output=True, text=True)
            duration_s = float(result.stdout.strip()) if result.returncode == 0 else 60.0
        except Exception:
            duration_s = 60.0

        timestamps = _sample_timestamps(duration_s, settings.ocr_fps)

        events = 0
        ocr = _get_ocr()
        for ts in timestamps:
            fr = _read_frame_at(seg.video_path, ts)
            if fr is None:
                continue
            frame, w, h = fr
            # EasyOCR returns list of [bbox, text, conf]
            results = ocr.readtext(frame)
            for box, text, conf in results:
                if not text or not text.strip():
                    continue
                # box is 4 points [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                x_min, y_min = float(max(0, min(xs))), float(max(0, min(ys)))
                x_max, y_max = float(min(w, max(xs))), float(min(h, max(ys)))
                bbox = [int(x_min), int(y_min), int(max(1, x_max - x_min)), int(max(1, y_max - y_min))]
                ve = VisualEvent(
                    id=None,
                    segment_id=UUID(segment_id),
                    segment_started_at=datetime.fromisoformat(segment_started_at_iso),
                    channel_id=seg.channel_id,
                    timestamp_offset=float(ts),
                    event_type='ocr',
                    bbox=bbox,
                    confidence=float(conf) if conf is not None else None,
                    data={"text": text.strip(), "lang": "ar"},
                )
                db.add(ve)
                events += 1
        db.commit()

    return {"ok": True, "events": events, "elapsed_ms": int((perf_counter() - start) * 1000)}


