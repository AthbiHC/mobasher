from __future__ import annotations

import os
from time import perf_counter
from typing import Optional

from celery import Celery
from pydantic_settings import BaseSettings
from prometheus_client import Counter, Histogram, start_http_server
import os as _os


class ASRSettings(BaseSettings):
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    model_name: str = os.environ.get("ASR_MODEL", "large-v3")
    device: str = os.environ.get("ASR_DEVICE", "cpu")  # cpu|cuda|mps
    beam_size: int = int(os.environ.get("ASR_BEAM", "5"))
    vad_enabled: bool = bool(int(os.environ.get("ASR_VAD", "1")))
    word_timestamps: bool = bool(int(os.environ.get("ASR_WORD_TS", "1")))
    condition_on_previous: bool = bool(int(os.environ.get("ASR_COND_PREV", "0")))
    initial_prompt: Optional[str] = os.environ.get("ASR_INITIAL_PROMPT")
    metrics_port: Optional[int] = (
        int(os.environ.get("ASR_METRICS_PORT", "0")) if os.environ.get("ASR_METRICS_PORT") else None
    )


settings = ASRSettings()
app = Celery("mobasher_asr", broker=settings.redis_url, backend=settings.redis_url)

# Global model cache for worker process
_MODEL = None

# Prometheus metrics (process-local)
ASR_TASK_ATTEMPTS = Counter(
    "asr_task_attempts_total", "Total task attempts", ["task", "channel_id"],
)
ASR_TASK_OUTCOMES = Counter(
    "asr_task_outcomes_total", "Task outcomes by status", ["task", "outcome", "channel_id"],
)
ASR_TASK_DURATION = Histogram(
    "asr_task_duration_seconds", "Task duration in seconds", ["task", "channel_id"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
)

if settings.metrics_port:
    try:
        start_http_server(settings.metrics_port)
    except Exception:
        # ignore exporter start failures to not crash worker
        pass


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as e:
            raise e
        _MODEL = WhisperModel(settings.model_name, device=settings.device)
    return _MODEL


def _resolve_audio_path(path_str: str) -> str:
    from pathlib import Path as _P
    # 1) If already absolute and exists
    p = _P(path_str)
    if p.is_absolute() and p.exists():
        return str(p)
    repo_root = _P(__file__).resolve().parents[2]
    ingestion_dir = repo_root / "mobasher" / "ingestion"
    candidates: list[_P] = []
    # 2) Resolve relative to repo root
    candidates.append((repo_root / path_str).resolve())
    # 3) Resolve relative to ingestion dir (handles ../data/... stored paths)
    candidates.append((ingestion_dir / path_str).resolve())
    # 4) If MOBASHER_DATA_ROOT set, try to remap anything after '/audio/' under that root
    data_root_env = os.environ.get("MOBASHER_DATA_ROOT")
    if data_root_env:
        try:
            dr = _P(data_root_env)
            parts = p.parts
            if "audio" in parts:
                idx = parts.index("audio")
                sub = _P(*parts[idx:])  # audio/YYYY-MM-DD/filename.wav
                candidates.append((dr / sub).resolve())
        except Exception:
            pass
    for c in candidates:
        if c.exists():
            return str(c)
    return str(p if p.is_absolute() else (repo_root / p))


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
    try:
        init_engine()
        with next(get_session()) as db:  # type: ignore
            seg = db.get(Segment, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
            if seg is None or not seg.audio_path:
                try:
                    raise RuntimeError("segment_missing_or_no_audio")
                except Exception as e:
                    ASR_TASK_OUTCOMES.labels(task="transcribe_segment", outcome="retry", channel_id=getattr(seg, "channel_id", "unknown")).inc()
                    raise self.retry(exc=e)

            # mark processing and increment attempts once we know channel_id
            ASR_TASK_ATTEMPTS.labels(task="transcribe_segment", channel_id=seg.channel_id).inc()
            try:
                seg.asr_status = "processing"
                db.add(seg)
                db.commit()
            except Exception:
                pass

            # Resolve audio path to absolute if needed
            audio_path = _resolve_audio_path(seg.audio_path)

            # Run ASR with faster-whisper
            try:
                model = _get_model()
            except Exception as e:
                ASR_TASK_OUTCOMES.labels(task="transcribe_segment", outcome="retry", channel_id=seg.channel_id).inc()
                raise self.retry(exc=e)
            engine_t0 = perf_counter()
            segments, info = model.transcribe(
                audio_path,
                beam_size=settings.beam_size,
                vad_filter=settings.vad_enabled,
                word_timestamps=settings.word_timestamps,
                language="ar",
                condition_on_previous_text=settings.condition_on_previous,
                initial_prompt=settings.initial_prompt,
            )
            engine_time_ms = int((perf_counter() - engine_t0) * 1000)
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
                engine_time_ms=engine_time_ms,
                words=[{
                    "start": getattr(s, "start", None),
                    "end": getattr(s, "end", None),
                    "text": s.text,
                } for s in segments] if settings.word_timestamps else None,
                # text_norm computed below
            )

            # Normalize Arabic text optionally and persist
            try:
                from camel_tools.utils.normalize import normalize_arabic  # type: ignore
                def _norm(t: str) -> str:
                    return normalize_arabic(t, alef=True, yah=True, ta=True)
            except Exception:
                def _norm(t: str) -> str:
                    return t

            from mobasher.storage.models import Transcript
            tr = db.get(Transcript, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
            if tr is not None:
                tr.text_norm = _norm(text)
                tr.engine_time_ms = engine_time_ms
                db.add(tr)
                db.commit()

        # success metrics
        ASR_TASK_OUTCOMES.labels(task="transcribe_segment", outcome="success", channel_id=seg.channel_id).inc()
        # mark completed
        try:
            from mobasher.storage.db import get_session as _gs
            from mobasher.storage.models import Segment as _Seg
            with next(_gs()) as db2:  # type: ignore
                s2 = db2.get(_Seg, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
                if s2 is not None:
                    s2.asr_status = "completed"
                    db2.add(s2)
                    db2.commit()
        except Exception:
            pass
        ASR_TASK_DURATION.labels(task="transcribe_segment", channel_id=seg.channel_id).observe(elapsed_ms / 1000.0)
        return {"ok": True, "elapsed_ms": elapsed_ms}
    except Exception:
        # channel_id might be unknown if failure occurred before seg fetched
        try:
            ch = seg.channel_id  # type: ignore[name-defined]
        except Exception:
            ch = "unknown"
        ASR_TASK_OUTCOMES.labels(task="transcribe_segment", outcome="error", channel_id=ch).inc()
        # mark failed
        try:
            from mobasher.storage.db import get_session as _gs
            from mobasher.storage.models import Segment as _Seg
            with next(_gs()) as db2:  # type: ignore
                from datetime import datetime as _dt
                from uuid import UUID as _UUID
                s2 = db2.get(_Seg, (_UUID(segment_id), _dt.fromisoformat(segment_started_at_iso)))
                if s2 is not None:
                    s2.asr_status = "failed"
                    db2.add(s2)
                    db2.commit()
        except Exception:
            pass
        raise


