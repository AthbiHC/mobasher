# Mobasher Project Phases

This document outlines the development phases, scope, deliverables, and acceptance criteria. Use it as a reference when planning and executing work.

## Phase 1: Repository Layer + Minimal API (Completed)
- Scope:
  - SQLAlchemy repository helpers for channels, recordings, segments, transcripts
  - FastAPI app with endpoints: /health, /channels, /recordings, /segments
  - Pagination (limit/offset) and status filters
  - Consistent error handling (JSON 500s)
  - CLI to run API (localhost by default; --public opt-in)
- Deliverables:
  - mobasher/storage/repositories.py (list/upsert helpers)
  - mobasher/api/* (app, routers, schemas, deps)
  - docs/API.md
- Acceptance:
  - Endpoints respond with paginated results and correct filters
  - API runs via `./scripts/mediaview api serve` bound to 127.0.0.1

## Phase 2: ASR Ingestion Pipeline
- Scope:
  - Celery worker(s) with Redis broker
  - faster-whisper integration; optional VAD trimming
  - Upsert transcripts by (segment_id, started_at)
  - Retry/backoff on failures; idempotent processing
  - CLI to start worker and enqueue backfills
  - Basic Prometheus metrics (processed, failed, latency)
- Deliverables:
  - mobasher/asr/worker.py (Celery app + task)
  - Settings for ASR model/device/beam/VAD/timestamps
  - CLI commands: `mediaview asr worker`, `mediaview asr enqueue ...`
- Acceptance:
  - A sample WAV transcribed end-to-end; transcript persisted
  - Re-running the task does not duplicate transcripts

## Phase 3: Vision Pipeline (OCR/Objects/Faces)
- Scope:
  - Frame sampler with per-stream FPS throttles
  - OCR (Arabic), object detection, face recognition
  - Events persisted with timestamps and metadata
  - Batch reprocessing CLI
- Deliverables:
  - mobasher/vision/* modules
  - Storage schema usage for visual_events; repo helpers
  - CLI: `mediaview vision reprocess ...`
- Acceptance:
  - Events appear for sample videos; queries list expected data

## Phase 4: Monitoring & Ops
- Scope:
  - Prometheus metrics across recorder/API/workers
  - Grafana dashboards and basic alerts
  - Structured logging; health checks for recorder/API
- Deliverables:
  - Metrics endpoints and dashboard JSON
  - docs/OPERATIONS.md (runbooks)
- Acceptance:
  - Dashboards show live metrics; alert rules trigger on synthetic conditions

## Phase 5: Storage & Retention Hardening
- Scope:
  - Optional S3/MinIO media archive
  - Lifecycle/retention jobs and disk watermark cleanup
  - Backfill/migration tools
- Deliverables:
  - Retention jobs and configuration
  - docs/STORAGE.md with S3/MinIO setup
- Acceptance:
  - Media rotation works; disk thresholds enforced; backfills reproducible

## Phase 6: Minimal Web UI
- Scope:
  - Channel status, segments timeline, transcript viewer, basic search UI
  - Integrate with Phase 1 API
  - Simple auth (optional)
- Deliverables:
  - web/ (or app/) minimal SPA
  - API integration and usage docs
- Acceptance:
  - UI shows live data and basic navigation; search returns expected results

## Phase 7: Performance & Scale-Up
- Scope:
  - Multi-channel concurrency and resource tuning (CPU/GPU/ffmpeg)
  - DB indexes and query optimizations
  - Load tests and scaling guidance
- Deliverables:
  - Load test scripts, index migrations, tuning guides
  - docs/PERFORMANCE.md
- Acceptance:
  - Meets baseline throughput/latency targets; documented scaling plan
