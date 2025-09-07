## Monitoring & Ops

### Stack
- Prometheus (scrapes API:8010, recorder:9108, ASR:9109)
- Grafana: pre-provisioned datasource and dashboard "Mobasher Overview"

### Metrics surfaced
- API: request count/latency histogram
- Recorder: running, segments total by media_type, heartbeats, collect latency
- ASR: task attempts, outcomes, duration histogram

### Bring-up
```bash
cd mobasher/docker
docker compose --profile monitoring up -d prometheus grafana
```

### Dashboards
- API Requests (1m), API Latency (p50/p90)
- Recorder Segments by Type, Heartbeats
- ASR Tasks/s, ASR Duration (p50/p90), ASR Outcomes

### Alerts (future)
- Queue lag, no heartbeats, high API error rate, zero transcripts for N minutes


