# Mobasher Technical Stack (Detailed)

This document describes the end-to-end technical stack for Mobasher, covering ingestion, storage, API, workers, ASR, vision, monitoring, and operations. It is the single reference for technologies, configurations, and design choices.

## 1) Ingestion (Recorder)
- Runtime: Python (asyncio) wrapper launching `ffmpeg` as subprocesses for audio/video/archive.
- Input: HLS live streams per channel with custom headers; automatic reconnect flags.
- FFmpeg flags (high level):
  - Reconnect: `-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5`
  - Audio (WAV, mono, 16 kHz, 60s segments): `-vn -ac 1 -ar 16000 -c:a pcm_s16le -f segment -segment_time 60 -reset_timestamps 1 -strftime 1`
  - Video (MP4, H.264, segmenting): `-an -c:v libx264 -preset veryfast|realtime -g 2*fps -keyint_min fps -force_key_frames expr:gte(t,n_forced*segment_secs) -f segment ...`
  - Archive (hourly MP4), faststart and fragment options for progressive playback.
- Process lifecycle:
  - Child processes (ffmpeg) spawned in their own process group; recorder catches SIGINT/SIGTERM/SIGHUP and kills the whole group.
  - Pipes silenced (`DEVNULL`) to avoid stalls.
- CPU tuning (macOS): prefer `h264_videotoolbox` for video if available; fall back to `libx264` with faster presets.
- Data layout: `data/{audio,video,archive}/YYYY-MM-DD/` with start-time-only filenames.

## 2) Storage
- DB: PostgreSQL 16 with TimescaleDB for hypertables; pgvector for vector embeddings.
- ORM: SQLAlchemy 2.x; Alembic for migrations.
- Core tables (summary):
  - `channels`: id, name, url, headers, active, created_at, updated_at.
  - `recordings` (hypertable): (id, started_at) PK, channel_id, ended_at, status, error_message, extra, created_at, updated_at.
  - `segments` (hypertable): (id, started_at) PK, recording_id, channel_id, ended_at, audio_path, video_path, file_size_bytes, status, extra, created_at, updated_at.
    - Pipeline fields: `asr_status/last_processed_at/attempts`, `vision_status/last_processed_at/attempts`.
  - `transcripts`: (segment_id, segment_started_at) PK, language, text, words (JSON), confidence, model_name, model_version, processing_time_ms, created_at, updated_at.
  - `segment_embeddings`: (segment_id, segment_started_at) PK, model_name, vector (pgvector), created_at, updated_at.
  - `visual_events` (hypertable): id PK (+ created_at), segment_id, segment_started_at, channel_id, timestamp_offset, event_type (ocr|face|object|logo|scene_change), bbox [x,y,w,h], confidence, data JSON, created_at, updated_at.
  - `system_metrics` (hypertable): id PK (+ timestamp), metric_name, metric_value, tags JSON, optional channel_id.
- Indices: time/chan indices on recordings/segments/events; embedding similarity via pgvector operators.
- Migration pattern for Timescale hypertables: add nullable → backfill → set NOT NULL to satisfy columnstore constraints.

## 3) API (FastAPI)
- Endpoints (Phase 1): `/health`, `/channels` (paginated), `/recordings` (paginated + filters), `/segments` (paginated + filters), `/transcripts` (segment+transcript pairs, paginated + filters).
- Pagination: offset/limit; meta includes `next_offset`.
- Error handling: unified JSON 500.
- Binding: defaults to `127.0.0.1`; `--public` to bind `0.0.0.0` (no auth by default; keep internal).

## 4) Workers & Scheduler
- Celery + Redis broker; workers run ASR/vision tasks.
- Concurrency: configurable; default low for large models on CPU (e.g., `-c 2`).
- Scheduler: periodic enqueue with exponential backoff + jitter on errors; resets interval on success.
- Dedupe: Redis keys `asr:queued:{segment_id}:{started_at}` with TTL to prevent repeated enqueues.

## 5) ASR Stack
- Engine: faster-whisper (CTranslate2 backend).
- Models: `small`, `medium`, `large-v3` (recommended for accuracy). Arabic language forced via `language='ar'`.
- Tunables:
  - `ASR_MODEL` (e.g., `large-v3`), `ASR_DEVICE` (cpu|cuda; current env: cpu), `ASR_BEAM` (5–8 good range), `ASR_VAD` (0 recommended for broadcast narration), `ASR_WORD_TS` (off unless alignment needed).
  - `condition_on_previous_text` (optional accuracy boost on continuous speech); `initial_prompt` for domain priming.
- Telemetry: `processing_time_ms` (task wall clock), `model_version` (`fw-x|ct2-y`).
- Output persistence: `transcripts` upsert by `(segment_id, segment_started_at)`; idempotent.
- Optional enhancements:
  - WhisperX alignment & diarization for better timestamps/speaker turns.
  - Arabic text normalization post-step.
  - Split timing into `engine_time_ms` vs `total_time_ms` if needed.

## 6) Vision Stack
- Frame sampler: per-task FPS caps (e.g., OCR=1–3 fps, objects=2 fps, faces=1 fps).
- OCR (Arabic): EasyOCR currently integrated; region-of-interest (ROI) bands for `headline`, `ticker`, `center` plus full frame.
- OCR preprocessing: grayscale → CLAHE → slight blur → OTSU threshold → invert.
- OCR outputs:
  - Raw detections: one event per detected box with `data.text`, `data.region`.
  - Aggregated per region per frame: merged `bbox`, concatenated `text`, `font_px` (bbox height proxy), `tokens[]` with individual boxes.
  - Screenshots: saved per region using `<video-base>-seg_<index>_<region>.jpg` for QC.
- Object detection: YOLOv8/YOLOv10 (ultralytics) for people, vehicles, logos, UI elements.
  - Task: `vision.objects_segment`; config: `objects_fps`, `yolo_model`, `objects_conf_threshold`, `objects_classes`.
  - Writes `event_type='object'` with `data.class`, `bbox`, `confidence`; screenshots `<video-base>-seg_<index>_objects.jpg`.
- Face recognition: InsightFace (SCRFD detect + ArcFace embeddings) with cosine matching against a gallery.
  - Task: `vision.faces_segment`; config: `faces_fps`, `faces_det_thresh`, `faces_rec_thresh`, `faces_model`, `faces_gallery_dir`.
  - Write `event_type='face'` with `data.identity` and `confidence`; screenshots `<video-base>-seg_<index>_faces.jpg`.
- Face recognition: InsightFace; gallery-based identity matching.
- Optional: scene change detection for program segmentation.
- Post-processing: deduplicate near-identical events, temporal smoothing, normalized boxes.
- Output: rows in `visual_events` with `event_type`, `timestamp_offset`, `bbox`, `confidence`, and `data` JSON (e.g., `{text: ..., lang: ar}` for OCR; `{identity: ..., score: ...}` for faces).
- Pipeline flags updated in `segments` (`vision_status/...`).

## 7) Monitoring & Ops
- Metrics: Prometheus client planned across recorder/API/ASR/vision (processed counts, durations, errors).
- Dashboards: Grafana for throughput/latency per pipeline; basic alerting for stalls.
- Logs: structured logging; worker and recorder logs on disk.

## 8) Infra & Dev
- Docker Compose services: Postgres + TimescaleDB, Redis.
- Python: `mobasher/venv` virtual environment; dependencies pinned in `mobasher/requirements.txt`.
- CLI (Typer): `./scripts/mediaview` wrapper; commands for recorder, API, services, db, tests, asr (worker/ping/enqueue/scheduler/bench).
- Testing: pytest and Testcontainers for DB integration.
- Migrations: Alembic (`alembic revision --autogenerate`, `alembic upgrade head`).

## 9) Security & Access
- API is internal by default (127.0.0.1). When exposed, place behind reverse proxy with auth (Basic/Bearer) and CORS policy.
- DB access restricted to local compose network.

## 10) Performance Strategy
- ASR:
  - Accuracy-first: `large-v3`, beam 5–8, VAD off.
  - Throughput-first: `medium`, beam 5–8, VAD off; reprocess important windows with `large-v3`.
  - Concurrency tuned to hardware; on CPU, keep low (e.g., 1–2).
- Vision:
  - FPS caps per detector; batched inference where supported; model size trade-offs.
- Scheduler: dedupe + backoff to avoid overload; incremental batches.

## 11) Configuration
- Channel YAML: stream URL, headers; recording options (segment length, qualities); audio/video settings; storage directories; vision thresholds; face gallery path.
- Environment:
  - DB: `DB_HOST/PORT/NAME/USER/PASSWORD/SSLMODE`.
  - ASR: `ASR_MODEL/DEVICE/BEAM/VAD/WORD_TS`.
  - Redis: `REDIS_URL`.
  - Data root: `MOBASHER_DATA_ROOT`.

## 12) Interfaces and Queries (Examples)
- API queries:
  - `/transcripts?channel_id=&since=&limit=&offset=`
  - `/segments?channel_id=&start=&end=&status=&limit=&offset=`
  - `/visual-events?channel_id=&type=&start=&end=&limit=&offset=` (planned)
- DB examples:
  - Recent OCR text: select from `visual_events` where `event_type='ocr'` and `data->>'text' ILIKE '%keyword%'`.
  - Top faces: count by `data->>'identity'` per time bucket.

This document will evolve as we integrate vision and monitoring. For live commands and examples, see `docs/COMMANDS.md` and `docs/API.md`.
