## Continue Development Plan (Alpha Roadmap)

This document captures the proposed next steps to mature the Mobasher system from the current working baseline (API, recorder, ASR, partial vision) into a robust, operable, and scalable service.

### Objectives
- Productionize developer workflow and CI/CD
- Harden storage/indexing/retention
- Improve ingestion and archive robustness
- Complete ASR/vision pipelines and API polish
- Strengthen observability (metrics/dashboards/alerts)
- Prepare deployment runbooks and automation
- Start the NLP alerts feature (entities + phrase alerts)

---

### High‑Priority Workstreams

#### 1) CI/CD & Repository Hygiene
- GitHub Actions:
  - Lint (ruff/flake8), type‑check (mypy), tests (pytest), Alembic migration check, Docker build.
  - Cache Python deps; add matrix for macOS/Linux.
- Pre‑commit hooks: black/isort/ruff/mypy on commit.
- Remove committed `mobasher/venv/` from VCS; enforce `.gitignore`.
- Standardize config via `pydantic-settings`/`.env` and document env precedence.

Acceptance:
- PRs run CI; failing lints/tests block merge.
- `pre-commit` runs locally; no stray venv files appear in diffs.

#### 2) DB, Indexing, Retention
- Migrations:
  - Ensure `transcripts.text_norm` and `engine_time_ms` are present and backfilled where applicable.
  - Add indexes:
    - `segments (channel_id, started_at)`
    - `visual_events (channel_id, event_type, created_at)`
    - transcripts search: pg_trgm or FTS (text/text_norm), plus `(segment_id, segment_started_at)` already exists.
- Retention:
  - Wire `mobasher/storage/retention_jobs.py` to a scheduler (cron/systemd timer).
  - Document retention defaults and overrides.

Acceptance:
- Queries for recent segments, transcripts, and visual events meet baseline latency at 10–100k rows.
- Retention job dry‑run and `--yes` both operate correctly.

#### 3) Ingestion & Archive Robustness
- Channel YAML schema validation (segment length, qualities, headers) with clear errors.
- Recorder metrics/heartbeats and auto‑restart guidance.
- Archive recorder:
  - Verify top‑of‑hour cuts; add logs for mode (copy/encode), FPS/bitrate; unify archive path; thumbnail policy.

Acceptance:
- 24/7 recorder stability with reconnection.
- Hourly archive file generation confirmed on at least one channel.

#### 4) ASR Pipeline
- Keep scheduler as a managed service (systemd unit) with exponential backoff + dedupe TTL tuning.
- Optional diarization toggle; expand task metrics (queue time, engine time, total time).
- Tests for idempotency and the fixed transcripts pagination path.

Acceptance:
- New segments get transcripts without duplication; task success rate/latency visible in Grafana.

#### 5) Vision Pipeline
- OCR: finalize ROI/dedup thresholds; aggregated spans stable; populate confidence consistently.
- Objects: tune YOLO threshold/classes; add class filters to API.
- Faces: complete gallery path/envs; thresholds; small gallery validation.
- Screenshot retention job with configurable policy.
- CLI: `mediaview vision reprocess --channel --since --ops ocr,objects,faces --fps N` (idempotent, resumable, summary).

Acceptance:
- `/visual-events` performant with indexes; screenshots present and rotated per policy.

#### 6) API Enhancements
- `/visual-events`:
  - Add counts endpoint and aggregated filters (by class/region/time window).
  - Performance pass and indexes.
- Authn/Z: API key or JWT + CORS policy; rate limits for public endpoints.
- OpenAPI polish; examples and error schemas.

Acceptance:
- Authenticated API with clear docs; `/visual-events` navigable and fast.

#### 7) Observability
- Ensure Prometheus metrics across recorder/API/ASR/vision (throughput, errors, durations).
- Grafana: per‑channel dashboards (templated variables) and alert rules (no heartbeats, ASR lag, API errors).

Acceptance:
- Dashboards show live SLOs; alerts fire under synthetic failure.

#### 8) CLI Completeness
- Implement `docs/002-CLI-PLAN.md` backlog:
  - `vision reprocess`, JSON output (`--json`), `channels` helpers (list/add/enable/disable), improved log viewing/rotation.

Acceptance:
- Operators can run common flows via CLI with helpful output and `--json` for scripting.

#### 9) Testing
- E2E: ingest → ASR → vision → API happy path using small fixture media.
- Contract tests for repositories and API pagination/filters.
- Property tests for channel YAML validation.

Acceptance:
- CI runs e2e and unit tests reliably on every PR.

#### 10) Deployment & Runbooks
- Systemd services for API, recorders (per‑channel), ASR worker + scheduler, vision worker; Caddy/Nginx reverse proxy.
- Backup/restore runbook; environment bootstrap scripts.

Acceptance:
- Single‑node deployment repeatable; services restart automatically and are observable.

#### 11) NLP Alerts (Phase Kickoff)
- Schema: `entities` and `alerts` tables (see `docs/014-NLP-ALERTS.md`).
- Worker: Arabic NER + curated phrase matcher; Prometheus metrics.
- Grafana: entities/min by type/channel; alerts/min by category; recent alerts table.

Acceptance:
- Alerts generated in <60s end‑to‑end on curated phrases; entities stored and queryable.

---

### Suggested 2‑Week Roadmap

Week 1
- CI + pre‑commit; remove committed venv; normalize `.env` handling.
- DB indexes and migrations for transcripts/visual_events; retention job wiring.
- Vision screenshot retention; `/visual-events` indexes; `vision reprocess` CLI.
- Archive recorder verification/logging.

Week 2
- API auth/rate limiting; transcripts search endpoint (FTS/trigram) with examples.
- NLP alerts MVP (schema + worker + basic dictionaries; dry‑run mode).
- E2E test flows; systemd templates and deployment doc updates; dashboard/alerts pass.

---

### Risks & Mitigations
- CPU/GPU constraints: keep model sizes & concurrency tunable; allow task backoff.
- Storage growth: enforce retention policies; optional S3/MinIO for screenshots/archive.
- Unstable channels: add health checks and backoff logic per channel; alert on missing segments.

### Open Questions
- Preferred auth scheme (API key vs. JWT) and exposure strategy (internal vs. proxied public)?
- Screenshot retention targets and S3 offloading timeline?
- Entities/alerts scope for MVP (entity types, phrase lists, destinations)?


