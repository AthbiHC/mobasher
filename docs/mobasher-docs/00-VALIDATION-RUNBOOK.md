## Validation Runbook (End-to-End)

This document captures a reproducible, step-by-step plan to validate the Mobasher system locally, including real outputs, issues encountered, and their fixes.

### Prerequisites
- DO Droplet with managed Postgres/Redis services
- Python venv at `mobasher/venv` with project requirements installed
- Repo root: `/root/MediaView`
- Working directory: `/root/MediaView/mobasher`

### 1) Check managed services connectivity
```bash
cd /root/MediaView/mobasher
PYTHONPATH=. venv/bin/python -m mobasher.cli.main status
```
Expected: Redis: ok, DB: ok (managed services connected).

### 2) Verify Postgres readiness and schema
```bash
docker compose -f mobasher/docker/docker-compose.yml exec postgres pg_isready -U mobasher -d mobasher
docker compose -f mobasher/docker/docker-compose.yml exec postgres psql -U mobasher -d mobasher -c "select now();"
docker compose -f mobasher/docker/docker-compose.yml exec postgres psql -U mobasher -d mobasher -c "select extname from pg_extension where extname in ('timescaledb','vector');"
docker compose -f mobasher/docker/docker-compose.yml exec postgres psql -U mobasher -d mobasher -c "select hypertable_name from timescaledb_information.hypertables where hypertable_name in ('recordings','segments','visual_events','system_metrics');"
```
Expected: extensions include `timescaledb` and `vector`; required hypertables exist.

### 3) Verify Redis
```bash
docker compose -f mobasher/docker/docker-compose.yml exec redis redis-cli PING
```
Expected: `PONG`.

### 4) Fresh reset (full wipe)
```bash
cd /root/MediaView/mobasher
PYTHONPATH=. venv/bin/python -m mobasher.cli.main freshreset --yes
```
Expected: truncates DB (`recordings`, `segments`, `transcripts`, `visual_events`, `segment_embeddings`, `system_metrics`) and wipes data directories under the configured roots.

Notes:
- `freshreset` stops recorder/workers and closes common metrics ports.
- Channels are preserved by default (no `--include-channels` needed).
- All files (.wav, .mp4, .jpg) are properly cleaned up.

### 5) Start API and verify
```bash
# Preferred (uses venv automatically through mediaview wrapper):
./scripts/mediaview api serve --host 127.0.0.1 --port 8010 --reload

# Alternatively, explicitly with venv:
PYTHONPATH=. mobasher/venv/bin/python -m uvicorn mobasher.api.app:app --host 127.0.0.1 --port 8010 --reload

# Health check
curl -s http://127.0.0.1:8010/health
```
Expected: `{ "status": "ok" }`.

### 6) Start recorder and validate
```bash
./scripts/mediaview recorder start --config mobasher/channels/kuwait1.yaml --heartbeat 15 --metrics-port 9108 --daemon
./scripts/mediaview recorder status
curl -s http://127.0.0.1:9108/metrics | head
curl -s "http://127.0.0.1:8010/segments?channel_id=kuwait_news&limit=3" | jq '.items | length'
```
Expected: recorder PID exists; Prometheus metrics show `mobasher_recorder_running`; API returns new segments.

### 7) Start ASR worker, ping, enqueue, verify
```bash
# Start worker (solo pool for macOS; use venv)
./scripts/mediaview asr worker --pool solo --concurrency 1 --metrics-port 9109 &

# If CLI ping fails due to global python, use venv python directly:
PYTHONPATH=. mobasher/venv/bin/python -c "from mobasher.asr.worker import ping; print(ping.delay().get(timeout=10))"

# Enqueue missing transcripts (avoid zsh quoting pitfalls by using venv python):
PYTHONPATH=. mobasher/venv/bin/python -c "from mobasher.asr.enqueue import enqueue_missing; print(enqueue_missing('kuwait_news', None, 10))"

# Verify metrics and API
curl -s http://127.0.0.1:9109/metrics | grep -E "asr_task_(outcomes|attempts|duration)_" | cat
curl -s "http://127.0.0.1:8010/transcripts?channel_id=kuwait_news&limit=100" | jq '.items | length'
```
Expected: `pong`; ASR metrics show attempts/success; transcripts appear via API.

### 8) Vision (optional in this run)
```bash
source mobasher/venv/bin/activate
pip install ultralytics==8.3.67 easyocr==1.7.2
export MOBASHER_SCREENSHOT_ROOT=${MOBASHER_DATA_ROOT:-/Volumes/ExternalDB/Media-View-Data/data}/screenshot
./scripts/mediaview vision worker --concurrency 2 &
./scripts/mediaview vision enqueue --limit 10
curl -s "http://127.0.0.1:8010/visual-events?channel_id=kuwait_news&limit=5" | jq '.items | length'
```
Expected: visual events rows and screenshots under `screenshot/`.

### 9) Archive recorder (optional)
```bash
./scripts/mediaview archive start --config mobasher/channels/kuwait1.yaml --mode copy --metrics-port 9120 --daemon
./scripts/mediaview archive status
curl -s http://127.0.0.1:9120/metrics | head
./scripts/mediaview archive stop
```

### 10) Monitoring (optional)
```bash
cd mobasher/docker && docker-compose --profile monitoring up -d prometheus grafana
open http://localhost:9090/targets
open http://localhost:3000
```

---

## Issues encountered and fixes

### A) CLI used system Python instead of venv (ModuleNotFoundError: celery)
Symptom:
```bash
./scripts/mediaview asr ping
ModuleNotFoundError: No module named 'celery'
```
Cause: some one-liners ran with the system Python, not the project venv.
Fixes:
- Use `./scripts/mediaview` (it launches with `mobasher/venv/bin/python`).
- For ad‑hoc one‑liners, explicitly use venv:
```bash
PYTHONPATH=. mobasher/venv/bin/python -c "from mobasher.asr.worker import ping; print(ping.delay().get(timeout=10))"
```

### B) zsh argument quoting for `--channel-id`
Symptom:
```bash
./scripts/mediaview asr enqueue --channel-id 'kuwait_news'
NameError: name 'kuwait_news' is not defined
```
Cause: the CLI constructs an inline Python command; shell quoting can interfere.
Fixes:
- Avoid channel filter or call via venv Python directly:
```bash
PYTHONPATH=. mobasher/venv/bin/python -c "from mobasher.asr.enqueue import enqueue_missing; print(enqueue_missing('kuwait_news', None, 10))"
```

### C) API temporarily refused connections
Symptom:
```bash
curl -s http://127.0.0.1:8010/health  # connection refused
```
Fix:
Restart API with venv:
```bash
PYTHONPATH=. mobasher/venv/bin/python -m uvicorn mobasher.api.app:app --host 127.0.0.1 --port 8010 --reload &
```

### D) /transcripts?limit=5 returned 0 despite DB having transcripts
Cause: repository paged on newest segments first, then filtered by presence of transcript; the newest N segments hadn’t been transcribed yet.
Fix: change pagination to page over transcripts and join to segments.

Edit applied in `mobasher/storage/repositories.py` (function `list_recent_transcripts`):
- Order by `Transcript.segment_started_at` desc and join `Segment` on composite keys.
- After reload, `GET /transcripts?limit=5` returns items as expected.

---

## Quick verification checklist
- Docker: `./scripts/mediaview services ps` → up
- DB: `pg_isready`, extensions (timescaledb, vector), hypertables exist
- Fresh reset: completed
- API: `/health` OK
- Recorder: PID exists; metrics live; segments via API
- ASR: `pong`; metrics show attempts/success; transcripts via API
- Vision (optional): events via API; screenshots on disk
- Archive (optional): metrics and hourly files


