# Mobasher System Commands

This document catalogs common commands and workflows for developing, running, and maintaining Mobasher.

## 1) CLI

- Preferred usage via wrapper: `./scripts/mediaview --help`
- Examples:
  - Start recorder: `./scripts/mediaview recorder start --config mobasher/channels/kuwait1.yaml`
  - Status/Stop: `./scripts/mediaview recorder status` / `./scripts/mediaview recorder stop` (also cleans up lingering ffmpeg)
  - API server: `./scripts/mediaview api serve --host 127.0.0.1 --port 8001` (add `--public` to bind 0.0.0.0)
  - ASR worker (CPU, stable): `./scripts/mediaview asr worker` (requires Redis)
    - For lower parallelism: `PYTHONPATH=. mobasher/venv/bin/python -m celery -A mobasher.asr.worker.app worker -c 2 --loglevel=INFO`
    - Note: `ASR_DEVICE=metal` is not supported by faster-whisper here; use CPU or CUDA if available
  - ASR ping: `./scripts/mediaview asr ping`
  - ASR enqueue: `./scripts/mediaview asr enqueue --channel-id kuwait_news --since 2025-09-05T00:00:00Z --limit 50`
  - ASR scheduler: `./scripts/mediaview asr scheduler --interval 30 --lookback 10`
  - Truncate DB: `./scripts/mediaview db truncate --yes`
  - Retention: `./scripts/mediaview db retention --dry-run`

## 2) Repository Workflow (custom assistant commands)

- "push the push": Updates docs as needed, commits all changes, pushes to current branch, then creates and switches to the next sequential `alpha-XXX` branch.
- "sync docs": Updates README and docs (including `docs/CHANGES-LOG.md`) to reflect changes, commits with a docs message, and pushes to the current branch (no branch switching).
- "fresh branch": Creates a new branch with `feature/<name>` or `fix/<name>`.
- "status check": Shows git status, recent commits, and a quick project structure overview.
- "quick test": Runs basic validation (lint/format/tests) suitable for fast feedback.
- "deploy prep": Prepares a release (versions, configs, changelog, verification).

Note: These are workflow shortcuts we use with the assistant. Their effects are described above; when needed, use the concrete shell commands below.

## 3) Recorder

- Start background recorder (local dev):
```bash
cd mobasher/ingestion
source ../venv/bin/activate
# Optional: set data location on external disk
export MOBASHER_DATA_ROOT=/Volumes/ExternalDB/Media-View-Data/data/
nohup python recorder.py --config ../channels/kuwait1.yaml --data-root ${MOBASHER_DATA_ROOT:-../data} --heartbeat 15 > recorder.log 2>&1 &
```
- Stop recorder (preferred):
```bash
./scripts/mediaview recorder stop
```

- Manual stop (fallback):
```bash
pkill -f 'ingestion/recorder.py' || true
# Also terminate any ffmpeg processes started by our recorder (identified by UA)
pkill -f "ffmpeg.*Mobasher/1.0" || true
```
- Tail logs:
```bash
cd mobasher/ingestion && tail -f recorder.log
```

- Check status (process running):
```bash
pgrep -af 'ingestion/recorder.py' || echo "Recorder not running"
```

## 4) Database

- DBeaver connection (local):
  - Host: localhost
  - Port: 5432
  - Database: mobasher
  - Username: mobasher
  - Password: mobasher
  - SSL: Disabled (local)

- Alembic migrations (from `mobasher/`):
```bash
source venv/bin/activate
alembic revision -m "message" --autogenerate
alembic upgrade head
```

- Truncate tables for a fresh start (from repo root):
```bash
source mobasher/venv/bin/activate
python -m mobasher.storage.truncate_db --yes                 # keeps channels
python -m mobasher.storage.truncate_db --yes --include-channels  # also clears channels
```

- Retention cleanup for transcripts/embeddings (non-hypertable):
```bash
source mobasher/venv/bin/activate
# Dry-run first
python -m mobasher.storage.retention_jobs --dry-run --retain-transcripts-days 365 --retain-embeddings-days 365
# Apply cleanup
python -m mobasher.storage.retention_jobs --yes --retain-transcripts-days 365 --retain-embeddings-days 365
```

- Environment variables (optional overrides):
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE`

## 5) Docker services (local dev)

- Start Postgres + Redis:
```bash
cd mobasher/docker
docker-compose up -d postgres redis
```
- Stop services:
```bash
docker-compose down
```

## 6) API

- Base URL (dev): `http://127.0.0.1:8001`
- See `docs/API.md` for endpoints and examples

## 7) Tests

- Install test dependencies (inside venv):
```bash
source mobasher/venv/bin/activate
pip install -r mobasher/requirements.txt
```
- Run integration test (Testcontainers) from repo root:
```bash
PYTHONPATH=. mobasher/venv/bin/python -m pytest -q mobasher/tests/test_db_integration.py
```

## 8) General setup

- Create/activate venv and install packages:
```bash
cd mobasher
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- Apply all migrations:
```bash
cd mobasher
source venv/bin/activate
alembic upgrade head
```

## 8) Notes

- Recorder writes `recordings` and `segments` to DB by default.
- `pgvector` and TimescaleDB are used in dev; migrations ensure extensions/policies in the main DB.
- For quick local tests without Timescale features, use the Testcontainers integration test which bootstraps a temporary Postgres and creates the ORM schema.
