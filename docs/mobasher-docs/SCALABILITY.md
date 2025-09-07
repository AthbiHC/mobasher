## Scalability & Performance

### Horizontal scaling
- Recorder: per-channel process on separate nodes (stateless aside from data root)
- ASR: multiple workers consuming from Redis; partition by channel or segment window
- API: scale replicas behind reverse-proxy/load balancer

### Storage considerations
- TimescaleDB hypertables with retention and compression policies
- S3/MinIO for long-term media and screenshots (future)

### Performance tuning
- FFmpeg encoders/presets/threads tied to hardware
- `faster-whisper` model size vs. latency/quality trade-offs; beam size; VAD
- Batch enqueue and concurrency control via Celery workers

### Observability-driven
- Use Prometheus histograms for latency and throughput SLOs
- Identify CPU/mem hotspots via exporters and dashboards


