from __future__ import annotations

import os
from time import perf_counter
from typing import Optional

from celery import Celery
from pydantic_settings import BaseSettings


class ASRSettings(BaseSettings):
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    model_name: str = os.environ.get("ASR_MODEL", "large-v3")
    device: str = os.environ.get("ASR_DEVICE", "cpu")  # cpu|cuda|mps
    beam_size: int = int(os.environ.get("ASR_BEAM", "5"))
    vad_enabled: bool = bool(int(os.environ.get("ASR_VAD", "1")))
    word_timestamps: bool = bool(int(os.environ.get("ASR_WORD_TS", "1")))


settings = ASRSettings()
app = Celery("mobasher_asr", broker=settings.redis_url, backend=settings.redis_url)

# Global model cache for worker process
_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as e:
            raise e
        _MODEL = WhisperModel(settings.model_name, device=settings.device)
    return _MODEL


@app.task(name="asr.ping")
def ping() -> str:
    return "pong"


@app.task(name="asr.transcribe_segment", bind=True, max_retries=3, default_retry_delay=10)
def transcribe_segment(self, segment_id: str, segment_started_at_iso: str) -> dict:
    start = perf_counter()
    # Lazy import heavy deps inside task
    from datetime import datetime
    from uuid import UUID
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.repositories import upsert_transcript
    from mobasher.storage.models import Segment

    init_engine()
    with next(get_session()) as db:  # type: ignore
        seg = db.get(Segment, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
        if seg is None or not seg.audio_path:
            raise self.retry(exc=RuntimeError("segment_missing_or_no_audio"))

        # Run ASR with faster-whisper
        try:
            model = _get_model()
        except Exception as e:
            raise self.retry(exc=e)
        segments, info = model.transcribe(
            seg.audio_path,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_enabled,
            word_timestamps=settings.word_timestamps,
            language="ar",
        )
        # Collect text and compute a simple average confidence if present
        texts = []
        confidences = []
        for s in segments:
            texts.append(s.text)
            if getattr(s, "avg_logprob", None) is not None:
                confidences.append(float(s.avg_logprob))
        text = " ".join(t.strip() for t in texts).strip()
        confidence: Optional[float] = (sum(confidences) / len(confidences)) if confidences else None

        # Build model_version using library versions for traceability
        try:
            from importlib.metadata import version as _pkg_version  # type: ignore
            fw_v = _pkg_version("faster-whisper")
            ct2_v = _pkg_version("ctranslate2")
            model_version = f"fw-{fw_v}|ct2-{ct2_v}"
        except Exception:
            model_version = "unknown"

        elapsed_ms = int((perf_counter() - start) * 1000)

        upsert_transcript(
            db,
            segment_id=UUID(segment_id),
            segment_started_at=datetime.fromisoformat(segment_started_at_iso),
            text=text,
            language="ar",
            confidence=confidence,
            model_name=settings.model_name,
            model_version=model_version,
            processing_time_ms=elapsed_ms,
        )

    return {"ok": True, "elapsed_ms": elapsed_ms}


