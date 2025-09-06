# Mobasher Change Log

This document tracks noteworthy changes, fixes, and operational learnings. Keep entries concise and high-signal.

## How to use
- Add a new dated entry with an ISO 8601 timestamp for each meaningful change (code, config, infra, docs). Example: `2025-09-06T12:30:00Z`.
- Prefer bullet points with short explanations and impact.
- Reference files, commands, or PRs when relevant.

---

## 2025-09-06T00:00:00Z
- Recorder shutdown reliability: added SIGINT/SIGTERM/SIGHUP handlers and process-group kill to terminate child ffmpeg
- CPU usage reduction: default hardware encoder on macOS (`h264_videotoolbox`), configurable `video.encoder/preset/threads`
- CLI stop improvement: `mediaview recorder stop` also kills lingering ffmpeg matching `Mobasher/1.0` UA
- Docs synced: README, COMMANDS, Main-Document updated; sample `kuwait1.yaml` adjusted

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
