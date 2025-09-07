## ASR (Automatic Speech Recognition)

### Overview
ASR is powered by `faster-whisper` (CTranslate2 backend). It processes audio segments to produce transcripts, with optional normalization, and stores timing/engine metrics for analysis.

### Components
- Worker (`mobasher/asr/worker.py`): Celery app with lazy model loading, Prometheus exporter, and task metrics
- Enqueue (`mobasher/asr/enqueue.py`): Adds missing segments to the queue (deduped)
- Scheduler (`mobasher/asr/scheduler.py`): Periodically enqueues recent missing/new segments
- Bench (`mobasher/asr/bench.py`): Model/params benchmarking with WER/CER

### Task: `asr.transcribe_segment`
- Resolves segment audio path to absolute (supports `MOBASHER_DATA_ROOT`)
- Runs model with configured `beam_size`, `vad_filter`, `word_timestamps`, `condition_on_previous_text`, `initial_prompt`
- Aggregates text and average confidence; writes `Transcript` including `model_version`, `processing_time_ms`, `engine_time_ms`, and optional per-word spans
- Normalizes Arabic text (`text_norm`) when `camel_tools` is available

### Settings
Environment variables:
- `ASR_MODEL` (default `large-v3`), `ASR_DEVICE` (`cpu|cuda|mps`), `ASR_BEAM`, `ASR_VAD`, `ASR_WORD_TS`, `ASR_COND_PREV`, `ASR_INITIAL_PROMPT`
- `ASR_METRICS_PORT` (Prometheus exporter)

### CLI
```bash
./scripts/mediaview asr worker --pool solo --concurrency 1 --metrics-port 9109
./scripts/mediaview asr enqueue --limit 100
./scripts/mediaview asr scheduler --interval 30 --lookback 20
```

### Metrics
- `asr_task_attempts_total{task}`
- `asr_task_outcomes_total{task,outcome}` (success|error|retry)
- `asr_task_duration_seconds_bucket{task}` histogram

### Data model
- `transcripts(segment_id, segment_started_at)` PK; `text`, `text_norm`, `language`, `confidence`, `model_name`, `model_version`, `processing_time_ms`, `engine_time_ms`, `words JSONB`

### Operational notes
- On macOS, use `-P solo` to avoid fork issues; on Linux, `prefork` or `threads` are fine
- Ensure `MOBASHER_DATA_ROOT` is consistent between recorder and ASR


