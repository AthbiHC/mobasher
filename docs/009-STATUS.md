# Project Status Snapshot

Timestamp: 2025-09-07T19:20:00Z
Branch: alpha-014

## Phase progress
- Phase 1 (API/Repos): done.
- Phase 2 (ASR): done + options (cond_prev, initial_prompt, word_ts, normalization, bench WER/CER). Migration pending for `transcripts.text_norm` and `engine_time_ms` (added in models).
- Phase 3 (Vision):
  - OCR: ROI bands + preprocessing; per‑region screenshots; aggregated spans with start/end; confidence populated; dedup/smoothing implemented.
  - Objects: YOLOv8 task added; running and writing `event_type=object`.
  - Faces: InsightFace task scaffolded; runtime installed; model pack downloading; gallery support ready.
  - API: `/visual-events` with filters (channel, type, region, time, q, min_conf).

## Runtime notes
- Recorders running on external data root: `/Volumes/ExternalDB/Media-View-Data/data`.
- New archive recorder (hour-aligned) writing to `data/archive/<channel>/<YYYY-MM-DD>/` with thumbnails.
- Fresh ops: `freshreset`, `kill-the-minions`. Recorder stop improved (kills ffmpeg and metrics ports).
 - Archive recorder check: after ~1h, no files found under `/Volumes/ExternalDB/Media-View-Data/data/archive/kuwait_news/2025-09-07` and process not running.

## Current TODOs (at time of snapshot)
- vision-faces-impl: Add face detection/recognition task (InsightFace SCRFD + ArcFace)
- vision-faces-test: Run one segment through face recognition and verify events
- vision-reprocess-cli: Create vision reprocess CLI (ops select, idempotent, summary)
- vision-screenshot-policy: Implement screenshot retention policy and cleanup job
- api-vision-polish: Add visual-events class filters, counts endpoint, and DB indexes

## Next session (short)
1) Verify archive recorder first hour cut + thumbnail creation (Kuwait).
2) Re-run archive in encode mode (or add debug logging) to ensure top-of-hour cuts; confirm output path.
3) Start/monitor recorders for target channels; validate Grafana v2 per-channel stats.
4) Review `docs/014-NLP-ALERTS.md`; decide NER model shortlist and start migrations for `entities`/`alerts`.
