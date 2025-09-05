# Mobasher Development Journal

This file tracks major decisions, progress, and context for maintaining continuity across development sessions.

## Project Overview
- **Name**: Mobasher (مباشر - "Live/Direct" in Arabic)
- **Purpose**: Real-time live TV analysis system for Arabic broadcasts
- **Repository**: https://github.com/AthbiHC/mobasher
- **Current Branch**: alpha-002

## Architecture Decisions

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
  - SQLAlchemy models for all tables
  - Database migration system with Alembic
  - Connection pooling and error handling

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
- 🔄 Database models and migration system
- 🔄 ASR pipeline with faster-whisper
- 🔄 Core workflow integration (recorder → DB → ASR)

### Next Steps
- 📋 Complete ASR worker implementation
- �� Implement processing queue and status tracking
- 📋 Create basic monitoring dashboard
- 📋 Add comprehensive error handling and logging

## Technical Notes

### Stream Access
- **Kuwait TV URL**: `https://kwtktv1ta.cdn.mangomolo.com/ktv1/smil:ktv1.stream.smil/chunklist.m3u8`
- **Required Headers**: Referer + User-Agent for CDN access
- **Stream Quality**: Multiple bitrates available, auto-selection working
- **Reliability**: Stable connection with proper reconnection logic

### Database Considerations
- **Hypertable Limitations**: No foreign keys between hypertables
- **Partitioning Strategy**: Daily partitions for segments and recordings
- **Retention Policies**: 1 year raw data, 90 days metrics
- **Compression**: 7-day delay for segments, 1-day for metrics

### Performance Optimizations
- **Audio Processing**: 16kHz mono for ASR efficiency
- **Segment Size**: 60 seconds balances latency vs. processing overhead
- **Indexing Strategy**: Time-based with channel filtering
- **Vector Search**: pgvector with planned IVFFlat indexing

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
