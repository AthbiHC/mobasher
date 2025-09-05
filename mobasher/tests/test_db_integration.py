import os
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

# Ensure repo root on path so 'mobasher' package resolves when tests run from anywhere
sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from mobasher.storage.db import DBSettings
from mobasher.storage.models import Base
from mobasher.storage.repositories import (
    upsert_channel,
    create_recording,
    complete_recording,
    upsert_segment,
    list_recent_recordings,
    upsert_transcript,
    upsert_embedding,
    semantic_search_segments_by_vector,
)


@pytest.mark.integration
def test_repositories_end_to_end_postgres_container():
    # Use an image that has pgvector preinstalled
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        url = pg.get_connection_url()
        # switch to psycopg driver
        url = url.replace("postgresql://", "postgresql+psycopg://")
        engine = create_engine(url, pool_pre_ping=True, future=True)
        TestingSessionLocal = sessionmaker(bind=engine, future=True)

        # Enable pgvector in the container, then create schema from models
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        # Create schema quickly from models (we skip Timescale features in container test)
        Base.metadata.create_all(bind=engine)

        with TestingSessionLocal() as db:  # type: Session
            # Channel
            ch = upsert_channel(
                db,
                channel_id="test_channel",
                name="Test Channel",
                url="http://example.com/stream.m3u8",
                headers={"User-Agent": "MobasherTest"},
            )
            assert ch.id == "test_channel"

            # Recording
            started_at = datetime.now(timezone.utc).replace(microsecond=0)
            rec = create_recording(db, channel_id=ch.id, started_at=started_at)
            assert rec.channel_id == ch.id

            # Segment
            seg_id_start = started_at
            seg = upsert_segment(
                db,
                segment_id=rec.id,  # reuse UUID for simplicity
                recording_id=rec.id,
                channel_id=ch.id,
                started_at=seg_id_start,
                ended_at=seg_id_start + timedelta(seconds=60),
                audio_path="/tmp/audio.wav",
                video_path=None,
                file_size_bytes=12345,
            )
            assert seg.audio_path == "/tmp/audio.wav"

            # Transcript
            tr = upsert_transcript(
                db,
                segment_id=seg.id,
                segment_started_at=seg.started_at,
                text="اختبار النظام باللغة العربية",
                language="ar",
                confidence=0.95,
                model_name="faster-whisper-test",
            )
            assert tr.text.startswith("اختبار")

            # Embedding (384-dim zero vector for smoke test)
            emb = upsert_embedding(
                db,
                segment_id=seg.id,
                segment_started_at=seg.started_at,
                model_name="sentence-transformers-test",
                vector=[0.0] * 384,
            )
            assert emb.model_name.startswith("sentence-transformers")

            # Complete recording
            rec2 = complete_recording(db, recording_id=rec.id, started_at=started_at)
            assert rec2 is not None and rec2.status == "completed"

            # List recent
            recent = list_recent_recordings(db, channel_id=ch.id, since=started_at - timedelta(minutes=5))
            assert any(r.id == rec.id for r in recent)

            # Semantic search
            results = semantic_search_segments_by_vector(
                db,
                query_vector=[0.0] * 384,
                top_k=3,
                model_name="sentence-transformers-test",
                channel_id=ch.id,
            )
            assert len(results) >= 1
            top_seg, distance = results[0]
            assert isinstance(distance, float)


