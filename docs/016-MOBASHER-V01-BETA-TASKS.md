## Mobasher v01 Beta Tasks

This document outlines the concrete tasks to deliver the v01 beta across four pillars:
CLI, Vision Screenshots, NLP over Transcripts, and a One‑Page Dashboard.

### Goals
- Central CLI to simplify operations (short commands, JSON output option).
- Finish screenshots pipeline (vision, no OCR) with retention and listing APIs.
- Add NLP (Arabic NER + curated phrases) on transcripts to power entity stats/alerts.
- One‑page dashboard with latest screenshots, health status, and entity word clouds.

---

## Milestones

### Milestone A: CLI core + Screenshots
- Add `console_scripts` entrypoint `mobasher` → `mobasher.cli.main:app`.
- New CLI commands:
  - `mobasher status` (Docker ps, DB ready, Redis ping, API /health, counts).
  - `mobasher channels list|add|enable|disable`.
  - `mobasher screenshots latest [--limit N] [--channel-id <id>]`.
  - `mobasher vision enqueue --ops screenshots --limit N`.
  - `mobasher ui serve [--host --port]` (dev helper).
  - All with optional `--json` output for scripting.
- Screenshots pipeline:
  - Task `vision.screenshots_segment(segment_id, started_at)` samples 1–3 frames and writes JPEGs to `MOBASHER_SCREENSHOT_ROOT/<channel>/<YYYY-MM-DD>/`.
  - Table `screenshots(id, channel_id, segment_id, segment_started_at, frame_timestamp_ms, screenshot_path, created_at)`.
  - Retention job for screenshots (days configurable).
- API endpoints:
  - `GET /screenshots?channel_id=&since=&limit=` (latest first; returns paths/URLs).

Acceptance:
- New segments generate screenshots; API lists latest across channels; CLI prints latest screenshots; retention job works in dry‑run and apply modes.

### Milestone B: NLP core (entities + phrases)
- Tables per `docs/014-NLP-ALERTS.md`:
  - `entities(id, segment_id, channel_id, started_at, ended_at, text, label, confidence, char_start, char_end, text_norm, model, created_at)`.
  - `alerts(id, channel_id, segment_id, matched_phrase, category, score, created_at, payload_json)`.
- Celery `nlp.worker` tasks:
  - `nlp.entities_for_transcript(...)` extracts Arabic entities from `text_norm`.
  - `nlp.alerts_for_transcript(...)` matches curated phrases (Aho–Corasick).
- Scheduler `nlp.scheduler` to poll recent transcripts.
- APIs for stats:
  - `GET /entities/stats?since=&until=` → counts by entity (for word cloud).
  - `GET /entities/stats_by_label?since=&until=` → counts grouped by label.

Acceptance:
- Entities and alerts created for new transcripts; stats endpoints power word clouds within acceptable latency.

### Milestone C: Dashboard + Health
- `GET /health/summary` computing green/orange/red from:
  - Recorder heartbeats (recent segments per channel),
  - ASR backlog (segments without transcripts),
  - DB/Redis/API reachability, optional worker pings.
- Static `/dashboard` (HTML+JS) with four boxes:
  - Latest screenshots grid (calls `/screenshots`).
  - Health status summary (calls `/health/summary`).
  - Entity word cloud (calls `/entities/stats?since=24h`).
  - Entity word cloud by category (calls `/entities/stats_by_label?since=24h`).

Acceptance:
- Page loads in <2s locally, boxes populated; refresh updates data.

### Milestone D: Polish
- CLI JSON output across commands; usage examples in docs.
- API OpenAPI examples, error schemas; auth (API key/JWT) + CORS; basic rate limiting.
- Indexes: `visual_events(channel_id,event_type,created_at)`, FTS/trigram on transcripts.
- Systemd templates; runbooks; Grafana panels for NLP.

---

## Implementation Details

### CLI
- Wire `console_scripts` in packaging to expose `mobasher`.
- Extend `mobasher/cli/main.py` with Typer subcommands; avoid fragile shell inlines; use Python calls directly.
- Add `--json` for machine‑readable output.

### Vision Screenshots
- Implement sampler (e.g., timestamps at 0.3, 0.6, 0.9 of segment duration).
- Save JPEGs; insert rows into `screenshots` table; include channel and frame timestamp.
- Retention job in `mobasher/storage/retention_jobs.py` extended to screenshots.

### NLP
- Start with CPU‑friendly Arabic NER; normalize text via `text_norm`.
- Phrase matcher via Aho–Corasick; YAML dictionaries under `data/dictionaries/alerts/`.
- Prometheus metrics for NLP tasks (durations, counts).

### API & Health
- `/screenshots` and NLP stats endpoints with pagination and filters.
- `/health/summary` aggregates DB/Redis/API checks plus pipeline freshness.

### Testing & Docs
- Unit tests for repos and stats; e2e for screenshots creation and stats endpoints.
- Update `docs/002-CLI-PLAN.md` and add how‑to sections to runbooks.

---

## Sequencing (2 Weeks)

Week 1:
- CLI entrypoint + status/channels/screenshots commands.
- Screenshots task + table + `/screenshots` API; retention job wiring.
- Indexes for speed; update docs and runbooks.

Week 2:
- NLP tables + worker + scheduler + stats APIs.
- `/health/summary` and `/dashboard` MVP.
- Tests, auth/CORS basics, systemd templates.


