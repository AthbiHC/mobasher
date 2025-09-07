## Multi-channel Architecture & Rollout Plan

### Architecture
- Recorder per channel (one process/unit each). DB writes and metrics include `channel_id`.
- Redis/Celery as shared broker; ASR/vision workers consume tasks labeled by `channel_id`.
- TimescaleDB for segments/events; S3/Block storage for media; API read endpoints filter by channel.
- Monitoring: Prometheus metrics labeled by `channel_id`, Grafana dashboards with channel selector.

### Data layout (proposed)
```
data/
  <channel_id>/
    audio/<YYYY-MM-DD>/*.wav
    video/<YYYY-MM-DD>/*.mp4
    screenshot/<YYYY-MM-DD>/*.jpg
```
Flag: `storage.channel_subdir: true` (default on). Recorder computes absolute paths under `data/<channel_id>/...`.

### Rollout (3 steps)
1) Implement `channel_subdir` in recorder; ship behind flag; keep legacy layout compatible.
2) Pilot: enable new layout for one channel; verify recorder/ASR/vision path resolution and metrics.
3) Migrate remaining channels; update docs/dashboards; set new layout as default.

### Scaling guidelines
- Start with 3–5 channels, 1–2 ASR workers; add workers per throughput target.
- Per-channel systemd units for recorders; optional worker pools pinned to channels.
- Alerts: missing heartbeats, ASR lag, API error rate per channel.

### Next actions
- Code: add `channel_subdir` and per-channel labels where missing; update Grafana variable.
- Ops: draft systemd templates for multiple recorders; document examples.

