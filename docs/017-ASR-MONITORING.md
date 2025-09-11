## ASR Monitoring and Throughput

### Start/Reset
```bash
# Stop workers/scheduler and clear queues
pkill -f 'celery.*mobasher.asr.worker' || true
pkill -f 'mobasher.asr.scheduler' || true
docker compose -f mobasher/docker/docker-compose.yml exec redis redis-cli FLUSHALL | cat

# Start worker (macOS):
ASR_MODEL=small ./scripts/mediaview asr worker --pool solo --concurrency 1 --metrics-port 9109 &
# Optional: second worker (use unique name/port):
ASR_MODEL=small ./scripts/mediaview asr worker --pool solo --concurrency 1 --metrics-port 9110 --name celery@asr2 &

# Start scheduler (uses venv python)
./scripts/mediaview asr scheduler --interval 15 --lookback 30 &
```

### Enqueue manually
```bash
./scripts/mediaview asr enqueue --limit 50
```

### Metrics endpoints
- Worker 1: `http://127.0.0.1:9109/metrics`
- Worker 2 (if running): `http://127.0.0.1:9110/metrics`

Key series:
- `asr_task_outcomes_total{task="transcribe_segment", outcome="success", channel_id="..."}`

### Quick throughput sample (segments/min)
```bash
# sample now
S1=$( (curl -s http://127.0.0.1:9109/metrics; curl -s http://127.0.0.1:9110/metrics 2>/dev/null) \
  | grep 'asr_task_outcomes_total{.*outcome="success"' | awk '{sum+=$NF} END{print sum+0}')
sleep 30
S2=$( (curl -s http://127.0.0.1:9109/metrics; curl -s http://127.0.0.1:9110/metrics 2>/dev/null) \
  | grep 'asr_task_outcomes_total{.*outcome="success"' | awk '{sum+=$NF} END{print sum+0}')
RATE=$(echo "($S2-$S1)*2" | bc)
echo "segments_per_minute=$RATE (delta=$(($S2-$S1)) in 30s)"
```

### Notes
- macOS: prefer `--pool solo -c 1` per worker process. Linux can use `--pool prefork -c N`.
- Use `ASR_MODEL=small` for higher throughput on CPU.
- The CLI scheduler and ping now run with the venv interpreter, so `redis` is available.


