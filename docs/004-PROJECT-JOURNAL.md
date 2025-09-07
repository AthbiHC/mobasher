# Mobasher Development Journal

This file tracks major decisions, progress, and context for maintaining continuity across development sessions.

## Project Overview
- **Name**: Mobasher (مباشر - "Live/Direct" in Arabic)
- **Purpose**: Real-time live TV analysis system for Arabic broadcasts
- **Repository**: https://github.com/AthbiHC/mobasher
- **Current Branch**: alpha-003

## Architecture Decisions
### 2025-09-06 - Recorder shutdown + FFmpeg CPU tuning
- Added signal handling (SIGINT/SIGTERM/SIGHUP) and process-group termination to ensure ffmpeg child processes exit cleanly
- Silenced ffmpeg stdio and avoided pipe buildup to reduce CPU overhead
- Introduced configurable encoder/preset/threads under `video` with macOS default to `h264_videotoolbox` (hardware); fallback `libx264` uses faster presets
- CLI `recorder stop` now also kills lingering ffmpeg processes matching `Mobasher/1.0` User-Agent


### 2024-12-19 - Project Structure
- **Decision**: Clean two-folder structure with only `docs/` and `mobasher/` in root
- **Rationale**: Clear separation of documentation and application code
- **Impact**: All modules organized within mobasher/ for scalability

### 2024-12-19 - Technology Stack
- **Database**: PostgreSQL 16 + TimescaleDB + pgvector
- **Queue**: Redis + Celery
- **AI/ML**: faster-whisper, YOLOv8, InsightFace, PaddleOCR
- **Observability**: Prometheus + Grafana + Loki
- **Language**: Python with FastAPI

### 2024-12-19 - Database Schema Design
- **Decision**: Use TimescaleDB hypertables with composite primary keys
- **Challenge**: Foreign key constraints between hypertables not supported
- **Solution**: Enforce referential integrity in application code
- **Impact**: Better time-series performance, requires careful data management

### 2024-12-19 - Stream Processing Architecture
- **Decision**: FFmpeg-based HLS recorder with async Python wrapper
- **Rationale**: Proven reliability for live stream capture
- **Implementation**: 60-second audio segments, robust reconnection logic
- **Impact**: Scalable foundation for multi-channel processing

## Development Progress

### Phase 1: Foundation (Completed)
- ✅ **Infrastructure Setup**
  - Docker environment with PostgreSQL + TimescaleDB + pgvector
  - Redis for task queuing
  - Virtual environment with core dependencies
  
- ✅ **Database Design**
  - Comprehensive schema with hypertables for time-series data
  - Support for channels, recordings, segments, transcripts, embeddings
  - Visual events table for computer vision results
  - Retention and compression policies configured

- ✅ **Stream Ingestion**
  - HLS recorder implementation (`ingestion/recorder.py`)
  - Kuwait TV stream integration with proper headers
  - Audio segmentation and file management
  - Channel configuration system (`channels/kuwait1.yaml`)

- ✅ **Testing & Validation**
  - Database connectivity verified
  - FFmpeg stream capture tested
  - Recorder initialization confirmed
  - End-to-end infrastructure operational

### Phase 2: Core Pipeline (Current)
- 🔄 **Database Integration**
  - SQLAlchemy models defined for all tables
  - Alembic initialized and baseline migration generated and applied
  - Connection pooling configured via SQLAlchemy engine
  - Recorder now persists `recordings` start/end and `segments` per file
  - Added migration `b6aa81e4e7b3` to allow nullable audio/video paths and require at least one

- 🔄 **ASR Pipeline**
  - faster-whisper setup with Arabic models
  - Celery worker implementation
  - Voice activity detection integration
  - Transcript storage and indexing

## Current Status

### Completed
- ✅ Project initialization and GitHub setup
- ✅ Clean project structure implementation
- ✅ Database infrastructure with TimescaleDB + pgvector
- ✅ HLS stream recorder with Kuwait TV integration
- ✅ Docker development environment
- ✅ FFmpeg installation and stream testing
- ✅ Channel configuration system
- ✅ Documentation framework and productivity commands

### In Progress
- 🔄 Database models and migration system (baseline applied)
- 🔄 ASR pipeline with faster-whisper
- 🔄 Core workflow integration (recorder → DB → ASR)

### Next Steps
- 📋 Complete ASR worker implementation
- 📋 Implement processing queue and status tracking
- 📋 Create basic monitoring dashboard
- 📋 Add comprehensive error handling and logging

## Technical Notes

### Stream Access
- **Kuwait News URL**: `https://kwtsplta.cdn.mangomolo.com/kb/smil:kb.stream.smil/chunklist.m3u8`
- **Required Headers**: Referer + User-Agent for CDN access
- **Stream Quality**: Multiple bitrates available, auto-selection working
- **Reliability**: Stable connection with proper reconnection logic

### Database Considerations
- **Hypertable Limitations**: No foreign keys between hypertables
- **Partitioning Strategy**: Daily partitions for segments and recordings
- **Retention Policies**: 1 year raw data, 90 days metrics
- **Compression**: 7-day delay for segments, 1-day for metrics

### Performance Optimizations
- **Recorder Heartbeat**: periodic logs of audio/video segment counts, with timestamps
- **Archive**: MP4 with faststart + fragmented moov; 60-minute chunks (playable when segment closes)

### Storage Path
- Data root can be overridden via `MOBASHER_DATA_ROOT`. Example external path: `/Volumes/ExternalDB/Media-View-Data/data/`.

### Persistence Behavior
- Inserts `Channel` on first use (upsert) to satisfy FK for `Recordings`
- `Segments` are upserted per time slice; `audio_path`/`video_path` are nullable but at least one must exist
- Only segments within the active run window are persisted

- **Audio Processing**: 16kHz mono for ASR efficiency
- **Segment Size**: 60 seconds balances latency vs. processing overhead
- **Indexing Strategy**: Time-based with channel filtering
- **Vector Search**: pgvector with planned IVFFlat indexing

### DBeaver Connection (Local Dev)
- Host: `localhost`
- Port: `5432`
- Database: `mobasher`
- Username: `mobasher`
- Password: `mobasher`
- Driver: PostgreSQL (TimescaleDB/pgvector extensions available)

## Development Workflow

### Branch Strategy
- `main`: Stable releases
- `alpha-XXX`: Development branches (alpha-001, alpha-002, etc.)
- `feature/xxx`: Feature development
- `fix/xxx`: Bug fixes

### Commit Convention
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation updates
- `refactor:` - Code refactoring
- `test:` - Test additions/updates
- `chore:` - Maintenance tasks

### Productivity Commands
- `"push the push"` - Update docs, commit, push, create next branch
- `"sync docs"` - Update documentation files
- `"status check"` - Show git status and project overview
- `"fresh branch"` - Create new feature branch

## Key Files for Context
- `README.md` - Project overview and setup
- `docs/Main-Document.md` - Comprehensive technical documentation
- `docs/PROJECT-JOURNAL.md` - Development progress tracking
- `docs/TODO.md` - Current priorities and tasks
- `mobasher/channels/kuwait1.yaml` - Sample channel configuration
- `mobasher/requirements.txt` - Python dependencies
- `mobasher/docker/docker-compose.yml` - Infrastructure setup
- `mobasher/storage/schema.sql` - Database schema
- `mobasher/ingestion/recorder.py` - HLS stream recorder

## Notes
- Always maintain this journal for major decisions
- Use productivity commands for efficient workflows
- Keep documentation synchronized with code changes
- Reference key files when starting new sessions
- Test infrastructure changes thoroughly before proceeding

## Next Session Priorities
1. **Database Models**: Create SQLAlchemy models for all tables
2. **ASR Setup**: Install and configure faster-whisper with Arabic models
3. **Pipeline Integration**: Connect recorder → database → ASR workflow
4. **Basic Monitoring**: Simple dashboard for system status

---

**Current Focus**: ASR pipeline integration and database model implementation
**Next Milestone**: End-to-end processing from live stream to transcript storage
