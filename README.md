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
├── docs/                 # Documentation
├── mobasher/            # Main application code
├── channels/            # Channel configuration files
├── ingestion/           # Stream capture and processing
├── asr/                 # Speech recognition workers
├── vision/              # Computer vision analysis
├── storage/             # Database models and management
└── monitoring/          # Observability and dashboards
```

## Getting Started

This project is currently in early development. Check the `docs/` folder for detailed documentation.

## Contributing

This is an open-source project focused on media transparency and accountability. Contributions are welcome!

## License

[License to be determined]

## Contact

For questions and collaboration opportunities, please open an issue on GitHub.
