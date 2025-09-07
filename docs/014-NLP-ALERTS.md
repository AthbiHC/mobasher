## Arabic NER and Real-time Alerts Plan

### Goals
- Extract named entities (PERSON, ORG, LOC, …) from Arabic transcripts.
- Trigger alerts when curated Arabic phrases appear in live transcripts per channel.
- Maintain <60s end-to-end latency from recording → transcript → NER/alerts.

### Model options (Arabic NER)
- CAMeL Tools NER (CAMeLBERT): solid MSA performance; Hugging Face inference.
- AraBERT/ArabicBERT NER variants: evaluate 2–3 checkpoints across entity types.
- Stanza Arabic NER: fallback baseline.
- Inference: Transformers pipeline (PyTorch). Optional ONNX Runtime export for CPU speed at scale.

### Text preprocessing
- Use existing `text_norm` (diacritics/orthography normalization) for matching.
- Keep original text and offsets. Run NER on normalized sentences (or 10–20s windows).
- Sentence segmentation for context and latency; map entity spans back if needed.

### Database schema
```
entities (
  id UUID PK,
  segment_id UUID,
  channel_id TEXT,
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  text TEXT,
  label TEXT,           -- PERSON/ORG/LOC/etc.
  confidence REAL,
  char_start INT,
  char_end INT,
  text_norm TEXT,
  model TEXT,           -- e.g., camelbert-ner-v1
  created_at TIMESTAMPTZ DEFAULT now()
)

alerts (
  id UUID PK,
  channel_id TEXT,
  segment_id UUID,
  matched_phrase TEXT,
  category TEXT,        -- politics/emergency/etc.
  score REAL,
  created_at TIMESTAMPTZ DEFAULT now(),
  payload_json JSONB    -- extra context/snippet/entities
)
```

### Processing topology
- New Celery `nlp` worker for NER + alerts.
- Enqueue on new `transcripts` (DB trigger/poller) with per-channel lookback.
- Metrics: `NER_TASK_DURATION`, `NER_ENTITIES_EXTRACTED`, `ALERTS_TRIGGERED` labeled by `channel_id`.

### Entity normalization / Linking (phase 2)
- Gazetteer pass (Arabic name variants) to canonicalize spans.
- Optional Wikidata reconciliation (Arabic labels + type), cached locally.

### Curated phrase alerts
- Structure: `data/dictionaries/alerts/*.yaml`
  - Example:
    ```yaml
    category: politics
    phrases:
      - مجلس الأمة
      - ولي العهد
      - أرامكو
    ```
- Matching engine: Aho–Corasick over `text_norm` for O(n) matching across thousands of phrases.
- Options: whole-word boundaries; per-category thresholds; optional fuzzy (levenshtein≤1) for orthographic drift.
- Dedup/rate-limit: Redis keys `(channel, phrase)` with TTL (2–5m); cooldown per category to avoid storms.
- Notifications: pluggable Slack/Webhook/Email. Payload includes channel, timestamp, snippet, entities, matched phrases.

### Grafana
- Panels: entities/min by type/channel; alerts/min by category; time-to-alert; recent alerts table.
- Alerts: rules for spikes or silence (no entities/alerts) per channel.

### Performance targets
- Latency: <60s from audio to alert.
- Throughput: batch transcripts per channel per minute; ONNX for NER if needed.
- Warm models on startup; cache tokenizer/model on worker.

### Implementation steps
1) Schema/migrations: add `entities`, `alerts` tables; repositories.
2) Worker: `nlp` Celery app with NER pipeline; Prometheus exporter.
3) Enqueue: poll recent transcripts; store entities; export metrics.
4) Alerts: dictionary loader (hot-reload), Aho–Corasick matcher on `text_norm`; Redis dedupe; notifier plugins; metrics.
5) Dashboards: add entities/alerts panels to Grafana; optional alert rules.
6) QA: evaluate 2–3 Arabic NER models on labeled sentences; tune normalization and dictionaries.

### Risks & mitigations
- Dialectal Arabic: expand dictionaries; consider domain-tuned NER.
- OCR/ASR noise: use normalization + fuzzy; alert cooldowns to reduce false positives.
- Latency spikes: ONNX/quantization; reduce batch size; scale `nlp` workers.

### Example metrics (Prometheus)
- `mobasher_ner_tasks_total{channel_id,model}`
- `mobasher_ner_entities_total{channel_id,label}`
- `mobasher_alerts_total{channel_id,category}`
- `mobasher_ner_task_duration_seconds_bucket{channel_id}` (histogram)

### Deliverables
- Migrations for `entities`/`alerts`
- `mobasher/nlp/worker.py` with NER and alert pipelines
- Dictionary YAMLs under `data/dictionaries/alerts/`
- Grafana panels for entities/alerts, with channel templating
- Runbooks for adding phrases and testing alerts


