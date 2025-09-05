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
git checkout alpha-001

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

For detailed documentation, check the `docs/` folder.

## Contributing

This is an open-source project focused on media transparency and accountability. Contributions are welcome!

## License

[License to be determined]

## Contact

For questions and collaboration opportunities, please open an issue on GitHub.
