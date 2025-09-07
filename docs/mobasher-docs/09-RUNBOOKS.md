## Operational Runbooks

### Recorder down / no segments
1. Check process: `./scripts/mediaview recorder status`
2. Logs: `tail -n 200 mobasher/ingestion/recorder.log`
3. Restart: `./scripts/mediaview recorder stop && ./scripts/mediaview recorder start --config mobasher/channels/kuwait1.yaml`

### ASR backlog grows / no transcripts
1. Worker logs: `tail -n 200 /tmp/asr.out`
2. Ensure worker up: `pgrep -af 'celery.*mobasher.asr.worker'`
3. Enqueue backlog: `./scripts/mediaview asr enqueue --limit 1000`
4. Add worker: another `./scripts/mediaview asr worker --pool solo --concurrency 1`

### API not responding
1. Check: `curl -s http://127.0.0.1:8010/metrics | head`
2. Restart service (systemd or CLI)

### Prometheus targets down
1. Visit `http://localhost:9090/targets`
2. Check exporters (8010, 9108, 9109)
3. Restart services and verify firewall


