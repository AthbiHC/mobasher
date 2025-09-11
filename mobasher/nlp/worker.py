from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple
from time import perf_counter

from celery import Celery
from pydantic_settings import BaseSettings
from prometheus_client import Counter, Histogram, start_http_server


class NLPSettings(BaseSettings):
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    metrics_port: Optional[int] = (
        int(os.environ.get("NLP_METRICS_PORT", "0")) if os.environ.get("NLP_METRICS_PORT") else None
    )
    # Dictionaries
    alerts_dir: str = os.environ.get("ALERTS_DICTIONARIES_DIR", "data/dictionaries/alerts")
    entities_dir: str = os.environ.get("ENTITIES_DICTIONARIES_DIR", "data/dictionaries/entities")


settings = NLPSettings()
app = Celery("mobasher_nlp", broker=settings.redis_url, backend=settings.redis_url)


NLP_TASK_ATTEMPTS = Counter(
    "nlp_task_attempts_total", "NLP task attempts", ["task", "channel_id"],
)
NLP_TASK_OUTCOMES = Counter(
    "nlp_task_outcomes_total", "NLP outcomes by status", ["task", "outcome", "channel_id"],
)
NLP_TASK_DURATION = Histogram(
    "nlp_task_duration_seconds", "NLP task duration seconds", ["task", "channel_id"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30)
)

if settings.metrics_port:
    try:
        start_http_server(settings.metrics_port)
    except Exception:
        pass


def _load_alert_dictionaries() -> List[Tuple[str, List[str]]]:
    import glob
    import yaml  # type: ignore
    out: List[Tuple[str, List[str]]] = []
    for path in glob.glob(os.path.join(settings.alerts_dir, "*.yaml")):
        try:
            with open(path, "r") as f:
                obj = yaml.safe_load(f) or {}
                category = obj.get("category") or os.path.splitext(os.path.basename(path))[0]
                phrases = obj.get("phrases") or []
                phrases = [str(p).strip() for p in phrases if str(p).strip()]
                if phrases:
                    out.append((str(category), phrases))
        except Exception:
            continue
    return out


def _load_entity_dictionaries() -> List[Tuple[str, List[str]]]:
    import glob
    import yaml  # type: ignore
    out: List[Tuple[str, List[str]]] = []
    for path in glob.glob(os.path.join(settings.entities_dir, "*.yaml")):
        try:
            with open(path, "r") as f:
                obj = yaml.safe_load(f) or {}
                label = obj.get("label") or os.path.splitext(os.path.basename(path))[0]
                items = obj.get("items") or []
                items = [str(p).strip() for p in items if str(p).strip()]
                if items:
                    out.append((str(label), items))
        except Exception:
            continue
    return out


def _normalize_arabic(text: str) -> str:
    try:
        from camel_tools.utils.normalize import normalize_arabic  # type: ignore
        return normalize_arabic(text, alef=True, yah=True, ta=True)
    except Exception:
        return text


@app.task(name="nlp.entities_for_transcript", bind=True, max_retries=2, default_retry_delay=10)
def entities_for_transcript(self, segment_id: str, segment_started_at_iso: str) -> Dict[str, int]:
    start = perf_counter()
    from uuid import UUID
    from datetime import datetime
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.models import Transcript, Entity, Segment

    init_engine()
    with next(get_session()) as db:  # type: ignore
        tr = db.get(Transcript, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
        seg = db.get(Segment, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
        if tr is None or seg is None:
            raise self.retry(exc=RuntimeError("missing_transcript_or_segment"))

        NLP_TASK_ATTEMPTS.labels(task="entities_for_transcript", channel_id=seg.channel_id).inc()

        text = tr.text_norm or _normalize_arabic(tr.text or "")
        label_to_items = _load_entity_dictionaries()  # [(label, [items...])]
        created = 0
        if label_to_items:
            t = text or ""
            for label, candidates in label_to_items:
                for cand in candidates:
                    if not cand:
                        continue
                    idx = t.find(cand)
                    if idx >= 0:
                        ent = Entity(
                            segment_id=UUID(segment_id),
                            channel_id=seg.channel_id,
                            started_at=seg.started_at,
                            ended_at=seg.ended_at,
                            text=cand,
                            label=label,
                            confidence=None,
                            char_start=idx,
                            char_end=idx + len(cand),
                            text_norm=cand,
                            model="dict-v1",
                        )
                        db.add(ent)
                        created += 1
        else:
            # Fallback: simple token extraction by whitespace; keep top few unique tokens (>3 chars)
            tokens = [w for w in (text or "").split() if len(w) >= 4]
            seen = set()
            for w in tokens:
                if w in seen:
                    continue
                seen.add(w)
                ent = Entity(
                    segment_id=UUID(segment_id),
                    channel_id=seg.channel_id,
                    started_at=seg.started_at,
                    ended_at=seg.ended_at,
                    text=w,
                    label="TERM",
                    confidence=None,
                    char_start=None,
                    char_end=None,
                    text_norm=w,
                    model="heuristic-v1",
                )
                db.add(ent)
                created += 1
        if created:
            db.commit()
        NLP_TASK_OUTCOMES.labels(task="entities_for_transcript", outcome="success", channel_id=seg.channel_id).inc()
        NLP_TASK_DURATION.labels(task="entities_for_transcript", channel_id=seg.channel_id).observe(perf_counter() - start)
        return {"created": created}


@app.task(name="nlp.alerts_for_transcript", bind=True, max_retries=2, default_retry_delay=10)
def alerts_for_transcript(self, segment_id: str, segment_started_at_iso: str) -> Dict[str, int]:
    start = perf_counter()
    from uuid import UUID
    from datetime import datetime
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.models import Transcript, Segment, Alert

    init_engine()
    with next(get_session()) as db:  # type: ignore
        tr = db.get(Transcript, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
        seg = db.get(Segment, (UUID(segment_id), datetime.fromisoformat(segment_started_at_iso)))
        if tr is None or seg is None:
            raise self.retry(exc=RuntimeError("missing_transcript_or_segment"))

        NLP_TASK_ATTEMPTS.labels(task="alerts_for_transcript", channel_id=seg.channel_id).inc()
        text = tr.text_norm or _normalize_arabic(tr.text or "")
        dicts = _load_alert_dictionaries()
        created = 0
        for category, phrases in dicts:
            for phr in phrases:
                if not phr:
                    continue
                if (text or "").find(phr) >= 0:
                    al = Alert(
                        channel_id=seg.channel_id,
                        segment_id=UUID(segment_id),
                        matched_phrase=phr,
                        category=category,
                        score=None,
                        payload_json={"segment_started_at": segment_started_at_iso},
                    )
                    db.add(al)
                    created += 1
        if created:
            db.commit()
        NLP_TASK_OUTCOMES.labels(task="alerts_for_transcript", outcome="success", channel_id=seg.channel_id).inc()
        NLP_TASK_DURATION.labels(task="alerts_for_transcript", channel_id=seg.channel_id).observe(perf_counter() - start)
        return {"created": created}


