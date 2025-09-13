# Mobasher Change Log

This document tracks noteworthy changes, fixes, and operational learnings. Keep entries concise and high-signal.

## How to use
- Add a new dated entry with an ISO 8601 timestamp for each meaningful change (code, config, infra, docs). Example: `2025-09-06T12:30:00Z`.
- Prefer bullet points with short explanations and impact.
- Reference files, commands, or PRs when relevant.

---

## 2025-09-13T15:20:00Z
- **CRITICAL FIX**: Video encoder compatibility issue resolved for Linux systems
- **Issue**: Al Jazeera (and 4 other channels) using `h264_videotoolbox` (macOS-only), causing video recording failure
- **Fix**: Replaced with `libx264` encoder + `veryfast` preset across all channels (al_jazeera, al_arabiya, al_ekhbariya, cnbc_arabia, sky_news_arabia)
- **Impact**: All 6 channels now properly record both audio AND video on Linux
- **Verification**: Multi-channel test successful - 6 channels recording simultaneously at 50% CPU load
- **Storage**: Fixed volume mapping - data now uses 500GB attached volume instead of filling main filesystem
- **Performance**: System handling 6-channel deployment with excellent resource utilization (16-core CPU, 32GB RAM)
- **Architecture**: Complete fresh reset with proper volume integration and encoder standardization

## 2025-09-06T00:00:00Z
- Recorder shutdown reliability: added SIGINT/SIGTERM/SIGHUP handlers and process-group kill to terminate child ffmpeg
- CPU usage reduction: default hardware encoder on macOS (`h264_videotoolbox`), configurable `video.encoder/preset/threads`
- CLI stop improvement: `mediaview recorder stop` also kills lingering ffmpeg matching `Mobasher/1.0` UA
- Docs synced: README, COMMANDS, Main-Document updated; sample `kuwait1.yaml` adjusted
2025-09-07T19:05:00Z: Added archive recorder (hour-aligned, copy/encode) with thumbnail hook; new CLI commands `archive start|stop|status`, `freshreset`, and `kill-the-minions`. Improved `recorder stop` to close metrics and ffmpeg.

## 2025-09-06T00:00:01Z
- Phase 1 API: added FastAPI app with `/health`, `/channels`, `/recordings`, `/segments`
- Pagination & filters: offset-based pagination + status filters for recordings/segments
- Error handling: unified JSON 500 handler
- CLI: `mediaview api serve` defaults to 127.0.0.1; add `--public` flag
- Docs: added `docs/API.md` and updated references in README/COMMANDS

## 2025-09-06T00:00:02Z
- Phase 2 scaffold: Celery worker (`mobasher/asr/worker.py`) with Redis broker
- ASR tasks: `asr.ping`, `asr.transcribe_segment` (faster-whisper integration)
- Enqueue helper: `mobasher/asr/enqueue.py` with `enqueue_missing()`
- CLI: `mediaview asr worker|ping|enqueue`
  
## 2025-09-06T00:00:03Z
- ASR scheduler: polling service to enqueue recent missing transcripts
- CLI: `mediaview asr scheduler --interval 30 --lookback 10`
- Optimization: cache Whisper model in worker process for speed

## 2025-09-06T00:00:04Z
- Enqueue dedupe via Redis keys with TTL to avoid duplicate scheduling
- Scheduler exponential backoff with jitter and success reset

## 2025-09-06T00:00:05Z
- CLI: run Celery via current Python interpreter to avoid PATH issues
- Docs: clarify worker concurrency flags and device caveats (no 'metal' device)

## 2025-09-06T00:00:06Z
- Vision: add OCR worker (EasyOCR) and enqueue command, initial 1 fps → 3 fps
- Vision: frame sampling via OpenCV; events persisted to `visual_events`

## 2025-09-06T13:20:00Z
- Vision OCR improvements:
  - ROI-based OCR for `headline`, `ticker`, and `center` regions, plus full-frame fallback
  - Lightweight preprocessing (grayscale → CLAHE → blur → OTSU → invert) for better Arabic overlays
  - Per-region screenshots with descriptive names: `<video-base>-seg_<index>_<region>.jpg`
  - Aggregated sentences per region at each timestamp with merged `bbox`, `font_px` (approx), and `tokens`
  - Stored in `visual_events.data` with `region`, `aggregated=true`, `font_px`, `tokens[]`
- DB: enforced UTF-8 client encoding on all connections
- Ops: helper scripts used to truncate `visual_events` and clear screenshots for clean benchmarking
 - Docs: Added Phase 3 prioritized list to `PHASES.md`; commands updated for vision reprocess/reset

## 2025-09-06T13:50:00Z
- Vision: added YOLO-based object detection (`vision.objects_segment`) with configurable FPS/conf/classes
- Enqueue now runs objects alongside OCR; screenshots saved as `<video-base>-seg_<index>_objects.jpg`
- API: `/visual-events` endpoint with filters (channel, type, region, time, q, min_conf)

## 2025-09-06T14:20:00Z
- Vision: added InsightFace-based face recognition (`vision.faces_segment`), configurable thresholds and gallery
- Docs: updated TECH-STACK and COMMANDS for faces setup; PHASES marked as implemented

## 2025-09-12T12:59:00Z
- **DO Droplet Production Fix**: Fixed `DBSettings` model to ignore extra fields from .env using `model_config = {"extra": "ignore"}` 
- **Commands Verified**: Both `kill-the-minions` and `freshreset` now work without errors on DO droplet with managed services
- **Fresh Reset Behavior**: Confirmed `freshreset` preserves channels by default, cleans all files (.wav, .mp4, .jpg), and truncates DB tables properly
- **Production Ready**: Central CLI (`PYTHONPATH=. venv/bin/python -m mobasher.cli.main`) tested and working with managed Postgres/Redis services
