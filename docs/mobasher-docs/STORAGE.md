## Storage & Database

### Stack
- PostgreSQL 16 + TimescaleDB (hypertables for time-series), pgvector for embeddings
- SQLAlchemy ORM models in `mobasher/storage/models.py`
- Alembic migrations with Timescale-safe patterns (add nullable, backfill defaults, set NOT NULL)

### Key tables
- `channels`, `recordings`, `segments` (+ status fields for asr/vision), `transcripts`, `visual_events`, `segment_embeddings`

### Conventions
- UTC timestamps; UTF-8 client encoding enforced
- Composite PKs: `(id, started_at)` for segments/transcripts
- JSONB fields for flexible payloads (OCR spans, detection metadata)

### Operations
- Migrations: `alembic revision --autogenerate`, `alembic upgrade head`
- Truncate helper: `python -m mobasher.storage.truncate_db --yes`
- Retention jobs: `python -m mobasher.storage.retention_jobs --yes --retain-transcripts-days 365 --retain-embeddings-days 365`


