# Project Status Snapshot

Timestamp: 2025-09-06T14:30:00Z
Branch: alpha-011

## Phase progress
- Phase 1 (API/Repos): done.
- Phase 2 (ASR): done + options (cond_prev, initial_prompt, word_ts, normalization, bench WER/CER). Migration pending for `transcripts.text_norm` and `engine_time_ms` (added in models).
- Phase 3 (Vision):
  - OCR: ROI bands + preprocessing; per‑region screenshots; aggregated spans with start/end; confidence populated; dedup/smoothing implemented.
  - Objects: YOLOv8 task added; running and writing `event_type=object`.
  - Faces: InsightFace task scaffolded; runtime installed; model pack downloading; gallery support ready.
  - API: `/visual-events` with filters (channel, type, region, time, q, min_conf).

## Runtime notes
- Ultralytics installed; note numpy pin conflict (currently numpy 2.2.6). If YOLO import issues arise, pin numpy<2.0 for object runs.
- InsightFace installed; `buffalo_l` pack downloading (slow). Use `FACES_GALLERY_DIR` to enable identity matching.

## Current TODOs (at time of snapshot)
- vision-faces-impl: Add face detection/recognition task (InsightFace SCRFD + ArcFace)
- vision-faces-test: Run one segment through face recognition and verify events
- vision-reprocess-cli: Create vision reprocess CLI (ops select, idempotent, summary)
- vision-screenshot-policy: Implement screenshot retention policy and cleanup job
- api-vision-polish: Add visual-events class filters, counts endpoint, and DB indexes

## Next actions (short)
1) Finish InsightFace model download, confirm analyzer ready.
2) Provide/enroll gallery; run faces on one segment.
3) Add counts endpoint + indices; reprocess CLI.
