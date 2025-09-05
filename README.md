# Mobasher - Real-Time Live TV Analysis System

**Mobasher** (مباشر - "Live/Direct" in Arabic) is an open-source, real-time television analysis system designed to capture, process, and analyze live TV broadcasts from multiple channels simultaneously.

## Features

- **Multi-Channel Support**: Monitor multiple TV channels in parallel
- **Arabic Language Support**: Optimized for Arabic speech recognition and OCR
- **Real-Time Processing**: Live transcription and visual analysis
- **Comprehensive Analysis**: Audio transcription, object detection, face recognition, and OCR
- **Scalable Architecture**: Built with modern technologies for horizontal scaling

## Technology Stack

- **Database**: PostgreSQL 16 + TimescaleDB + pgvector
- **Message Queue**: Redis + Celery
- **AI/ML**: faster-whisper, YOLOv8, InsightFace, PaddleOCR
- **Backend**: Python, FastAPI, SQLAlchemy
- **Monitoring**: Prometheus + Grafana + Loki

## Project Structure

```
├── docs/                           # Documentation
│   ├── Main-Document.md            # Comprehensive technical documentation
│   ├── PROJECT-JOURNAL.md          # Development progress and decisions
│   └── TODO.md                     # Current priorities and tasks
└── mobasher/                       # Main application code
    ├── channels/                   # Channel configuration files
    ├── ingestion/                  # Stream capture and processing
    ├── asr/                        # Speech recognition workers
    ├── vision/                     # Computer vision analysis
    ├── storage/                    # Database models and management
    ├── orchestration/              # Celery tasks and scheduling
    ├── monitoring/                 # Observability and dashboards
    ├── analysis/                   # Content analysis and embeddings
    ├── data/                       # Runtime data storage
    │   ├── audio/                  # Audio segments
    │   └── recordings/             # Video recordings (optional)
    ├── state/                      # System state and metrics
    ├── docker/                     # Docker configurations
    ├── tests/                      # Test files
    └── requirements.txt            # Python dependencies
```

## Getting Started

### Prerequisites
- Python 3.9+
- Docker and Docker Compose
- FFmpeg
- CUDA-compatible GPU (recommended for optimal performance)

### Quick Setup
```bash
# Clone the repository
git clone https://github.com/AthbiHC/mobasher.git
cd mobasher

# Switch to development branch
git checkout alpha-003

# Set up Python environment
cd mobasher
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start infrastructure services
cd docker
docker-compose up -d postgres redis

# Configure your first channel
cp channels/kuwait1.yaml channels/my-channel.yaml
# Edit channels/my-channel.yaml with your stream URL
```

### Data location (external disk optional)
Set a custom data root via environment variable. Example for an external drive:
```bash
export MOBASHER_DATA_ROOT=/Volumes/ExternalDB/Media-View-Data/data/
```
If not set, the recorder defaults to `../data` relative to `mobasher/ingestion`.

### Database (Local Dev)
- Host: `localhost`
- Port: `5432`
- Database: `mobasher`
- Username: `mobasher`
- Password: `mobasher`

Apply migrations:
```bash
cd mobasher
source venv/bin/activate
alembic upgrade head
```

## Documentation

- **[Main Documentation](docs/Main-Document.md)** - Comprehensive technical overview
- **[Project Journal](docs/PROJECT-JOURNAL.md)** - Development progress and architectural decisions
- **[TODO List](docs/TODO.md)** - Current priorities and development roadmap

## Development Workflow
### Run recorder in background (local)
```bash
cd mobasher/ingestion
source ../venv/bin/activate
# Optional: set custom data root
# export MOBASHER_DATA_ROOT=/Volumes/ExternalDB/Media-View-Data/data/
nohup python recorder.py --config ../channels/kuwait1.yaml --heartbeat 15 > recorder.log 2>&1 &
# tail -f recorder.log
```

### Recorder status and stop
```bash
# Check if recorder process is running
pgrep -af 'ingestion/recorder.py' || echo "Recorder not running"

# Stop recorder
pkill -f 'ingestion/recorder.py' || true
```

### Truncate database tables (fresh start)
```bash
source mobasher/venv/bin/activate
python -m mobasher.storage.truncate_db --yes                 # keeps channels
python -m mobasher.storage.truncate_db --yes --include-channels  # also clears channels
```


This project uses productivity commands for efficient development:
- Context is maintained across sessions through structured documentation
- Progress is tracked in `docs/PROJECT-JOURNAL.md`
- Current priorities are managed in `docs/TODO.md`
- Branch naming follows `alpha-XXX` pattern for development

## Current Status

🔄 **In Development** - DB integration (recorder now writes `recordings` and `segments`)
📋 **Next Milestone** - Repository layer + ASR ingestion

See [TODO.md](docs/TODO.md) for detailed current priorities.

## Contributing

This is an open-source project focused on media transparency and accountability. Contributions are welcome!

## License

[License to be determined]

## Contact

For questions and collaboration opportunities, please open an issue on GitHub.
