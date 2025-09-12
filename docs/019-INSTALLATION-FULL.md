# Full Installation, Initialization, and Migration Guide

This guide describes a clean, reproducible way to install all Mobasher dependencies, initialize the database, and verify the stack using your .env.

## 0) Prerequisites
- Linux host with sudo
- Python 3.12
- Docker (optional for local Postgres/Redis)
- .env at /root/MediaView/.env (already configured)

## 1) System packages
Install multimedia and GUI-less libraries used by OpenCV/FFmpeg and similar runtime deps.
```bash
sudo apt update
sudo apt install -y ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 libxrender1
```

## 2) Python virtual environment
```bash
python3 -m venv /root/MediaView/mobasher/venv
source /root/MediaView/mobasher/venv/bin/activate
pip install --upgrade pip
```

## 3) Requirements (full)
Install all Python dependencies defined in `mobasher/mobasher/requirements.txt`.

Note: the package name is `av` (PyAV), not `pyav`.
```bash
cd /root/MediaView/mobasher
pip install -r mobasher/requirements.txt
```

If you face GPU driver limitations, you can replace `onnxruntime-gpu` with CPU runtime:
```bash
pip uninstall -y onnxruntime-gpu && pip install onnxruntime
```

## 4) Optional: Local infrastructure via Docker
Skip if you are using managed services (as configured in your .env).
```bash
cd /root/MediaView/mobasher/docker
docker compose up -d postgres redis
```

## 5) Database migrations
Alembic reads .env automatically through the package init. The DBSettings model now properly ignores extra fields from .env.
```bash
cd /root/MediaView/mobasher/mobasher
source ../venv/bin/activate
alembic upgrade head
```
If extensions are required by your schema, enable them in Postgres:
```
CREATE EXTENSION IF NOT EXISTS vector;
-- TimescaleDB only if provided by your service
```

## 6) API smoke test
```bash
cd /root/MediaView
source mobasher/venv/bin/activate
uvicorn mobasher.api.app:app --host 0.0.0.0 --port 8010 --workers 1 &
sleep 2
curl -s http://127.0.0.1:8010/health
```
You should see: `{ "status": "ok" }`

## 7) CLI status
```bash
PYTHONPATH=. mobasher/venv/bin/python -m mobasher.cli.main status --json
```
This summarizes DB, Redis, API, and recent pipeline activity.

## 8) Start workers (optional, heavy runtime)
Run these when you’re ready to process media at scale:
```bash
# ASR worker
./scripts/mediaview asr worker --pool solo --concurrency 1 --metrics-port 9109

# NLP worker
./scripts/mediaview nlp worker --pool solo --concurrency 1 --metrics-port 9112

# Vision worker
./scripts/mediaview vision worker --concurrency 2
```

## Troubleshooting
- If `pip install` fails on a specific wheel, ensure Python 3.12-compatible versions are being selected.
- Replace `onnxruntime-gpu` with `onnxruntime` if installing GPU runtime is not desired.
- Ensure your droplet/server IP is in the managed DB/Redis trusted sources and `DB_SSLMODE=require` is set for Managed Postgres.
- For OpenCV import issues, verify `ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 libxrender1` are installed.

## Notes
- All components now read environment from `/root/MediaView/.env` automatically.
- The CLI wrapper `./scripts/mediaview` uses the venv Python automatically when present.


