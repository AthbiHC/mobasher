# Mobasher Change Log

This document tracks noteworthy changes, fixes, and operational learnings. Keep entries concise and high-signal.

## How to use
- Add a new dated entry with an ISO 8601 timestamp for each meaningful change (code, config, infra, docs). Example: `2025-09-06T12:30:00Z`.
- Prefer bullet points with short explanations and impact.
- Reference files, commands, or PRs when relevant.

---

## 2025-09-06T00:00:00Z
- Recorder shutdown reliability: added SIGINT/SIGTERM/SIGHUP handlers and process-group kill to terminate child ffmpeg
- CPU usage reduction: default hardware encoder on macOS (`h264_videotoolbox`), configurable `video.encoder/preset/threads`
- CLI stop improvement: `mediaview recorder stop` also kills lingering ffmpeg matching `Mobasher/1.0` UA
- Docs synced: README, COMMANDS, Main-Document updated; sample `kuwait1.yaml` adjusted
