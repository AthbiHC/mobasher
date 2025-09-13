# Project Status Snapshot

Timestamp: 2025-09-13T15:20:00Z
Branch: staging-live

## Phase progress
- Phase 1 (API/Repos): ✅ **COMPLETE** - Full API operational with health checks, pagination, filtering
- Phase 2 (ASR): ✅ **COMPLETE** - Large-v3 model, Arabic language support, word timestamps, normalization
- Phase 3 (Vision): 🔄 **IN PROGRESS** - OCR operational, objects detection ready, faces detection scaffolded
- **Multi-Channel Deployment**: ✅ **PRODUCTION READY** - 6 channels recording simultaneously

## Critical Fixes Applied
- **Video Recording Fix**: Replaced macOS-only `h264_videotoolbox` with Linux-compatible `libx264` across all channels
- **Storage Architecture**: Properly integrated 500GB volume (/mnt/volume_ams3_03) replacing main filesystem usage
- **Encoder Standardization**: All 6 channels now use consistent `libx264 + veryfast` configuration

## Current Deployment Status
- **System Load**: 50% CPU utilization on 16-core system with 6 simultaneous channels
- **Memory Usage**: 4.6GB/32GB (86% available)
- **Storage**: 500GB volume with <1% usage, properly mounted and operational  
- **Channels Active**: 6/6 channels successfully recording audio + video
- **Service Ports**: API (8010), Recorders (9108-9113), Archives (9120-9125)

## Runtime Infrastructure
- **Data Root**: `/mnt/volume_ams3_03/mediaview-data/data/` (symlinked to local `data/`)
- **Archive**: 10-minute segments with thumbnails, copy mode for quality retention
- **Database**: TimescaleDB with proper retention policies and fresh reset capability
- **Monitoring**: Per-service metrics ports with Prometheus integration ready

## Current TODOs (at time of snapshot)
- vision-faces-impl: Add face detection/recognition task (InsightFace SCRFD + ArcFace)
- vision-faces-test: Run one segment through face recognition and verify events
- vision-reprocess-cli: Create vision reprocess CLI (ops select, idempotent, summary)
- vision-screenshot-policy: Implement screenshot retention policy and cleanup job
- api-vision-polish: Add visual-events class filters, counts endpoint, and DB indexes

## Next session (short)
1) Verify archive recorder first hour cut + thumbnail creation (Kuwait).
2) Re-run archive in encode mode (or add debug logging) to ensure top-of-hour cuts; confirm output path.
3) Start/monitor recorders for target channels; validate Grafana v2 per-channel stats.
4) Review `docs/014-NLP-ALERTS.md`; decide NER model shortlist and start migrations for `entities`/`alerts`.
