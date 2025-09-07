## Recorder

### Overview
The recorder ingests HLS streams and emits aligned 60s audio and video segments using FFmpeg, with robust process management, CPU tuning, and Timescale-backed persistence of `recordings` and `segments`.

### Responsibilities
- Continuously record a channel’s HLS input
- Produce 60s `.wav` and `.mp4` segments with start-only filenames
- Persist `recordings` and `segments` rows
- Export Prometheus metrics (running, segments, heartbeats, collection latency)

### Key implementation details
- Process group management and graceful SIGTERM handling to avoid orphaned FFmpeg
- macOS hardware encoding via `h264_videotoolbox` by default; CPU fallback `libx264`
- Start-only filename parsing to compute segment time windows
- Guardrails for partial/short segments and cleanup on stop
- Absolute path root via `MOBASHER_DATA_ROOT`; recorder resolves `../data` to absolute

### Configuration
`mobasher/channels/<channel>.yaml`
```yaml
id: kuwait_news
name: Kuwait News
input:
  url: https://example.com/hls.m3u8
  headers:
    User-Agent: Mobasher/1.0
recording:
  segment_seconds: 60
  video_enabled: true
  audio_enabled: true
video:
  encoder: h264_videotoolbox
  preset: realtime
  threads: 2
  qualities:
    "720p": { resolution: "1280x720", bitrate: "2500k", fps: 25 }
storage:
  date_folders: true
  directories: { audio: audio, video: video, archive: archive }
```

### CLI
```bash
./scripts/mediaview recorder start --config mobasher/channels/kuwait1.yaml --heartbeat 15 --metrics-port 9108
./scripts/mediaview recorder stop
./scripts/mediaview recorder status
./scripts/mediaview recorder logs -f
```

### Metrics
- `mobasher_recorder_running{channel_id}` gauge
- `mobasher_recorder_segments_total{channel_id,media_type}` counter
- `mobasher_recorder_heartbeats_total{channel_id}` counter
- `mobasher_recorder_collect_duration_seconds{channel_id}` histogram

### Failure modes & recovery
- Network hiccups: FFmpeg `-reconnect` options enabled
- Orphaned FFmpeg: stopped via process groups and CLI `recorder stop`
- Partial files: cleaned up on stop and via duration/size guards


