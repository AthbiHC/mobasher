## API

### Overview
FastAPI service with pagination, filtering, and unified error handling. Exposes `/metrics` for Prometheus.

### Schemas & endpoints
- Channels, recordings, segments, transcripts with offset/limit and filters
- `/visual-events` with filters: `channel_id`, `event_type`, `region`, `q`, `since/until`, `min_conf`

### Running
```bash
./scripts/mediaview api serve --host 127.0.0.1 --port 8010
curl -s http://127.0.0.1:8010/metrics | head
```

### Error handling
- Global exception handler returns JSON 500 with `error` and `detail`


