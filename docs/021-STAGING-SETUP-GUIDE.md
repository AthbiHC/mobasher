# Staging Environment Setup Guide

## Prerequisites

### Server Specifications
- **Recommended**: DigitalOcean CPU-Optimized 4 vCPUs, 8GB RAM ($84/mo)
- **Minimum**: 4 vCPUs, 8GB RAM
- **OS**: Ubuntu 22.04 LTS
- **Storage**: 50GB+ SSD

### Required Services
- PostgreSQL 16 with TimescaleDB extension
- Redis server
- Python 3.12+
- FFmpeg with HLS support

## Complete Setup Sequence

### 1. System Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3.12 python3.12-venv python3.12-dev \
    postgresql-16 postgresql-16-postgis-3 \
    redis-server \
    ffmpeg \
    git curl wget \
    build-essential pkg-config

# Install TimescaleDB
sudo apt install -y timescaledb-2-postgresql-16
sudo timescaledb-tune --quiet --yes
sudo systemctl restart postgresql
```

### 2. Database Setup
```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE mobasher;
CREATE USER mobasher WITH ENCRYPTED PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE mobasher TO mobasher;
ALTER USER mobasher CREATEDB;
\q
EOF

# Enable extensions
sudo -u postgres psql -d mobasher << EOF
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
\q
EOF
```

### 3. Project Setup
```bash
# Clone repository
cd /root
git clone <repository_url> MediaView
cd MediaView/mobasher

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Set up environment variables
cat > .env << EOF
# Database
DATABASE_URL=postgresql://mobasher:your_password_here@localhost:5432/mobasher
POSTGRES_DB=mobasher
POSTGRES_USER=mobasher
POSTGRES_PASSWORD=your_password_here

# Redis
REDIS_URL=redis://localhost:6379/0

# Data storage
MOBASHER_DATA_ROOT=/root/MediaView/mobasher/data

# API settings
API_HOST=0.0.0.0
API_PORT=8010

# ASR Configuration (Optimized for 4 vCPU)
ASR_MODEL=medium
ASR_DEVICE=cpu
ASR_BEAM=3
ASR_VAD=1
ASR_WORD_TS=1
ASR_METRICS_PORT=9109

# Archive settings
ARCHIVE_DURATION_MINUTES=10
EOF

# Make environment variables available
source .env
```

### 4. Database Migration
```bash
# Initialize database schema
PYTHONPATH=. venv/bin/python -m mobasher.storage.db

# Run migrations
PYTHONPATH=. venv/bin/python -m alembic upgrade head

# Verify database setup
PYTHONPATH=. venv/bin/python -c "
from mobasher.storage.db import get_session, init_engine
init_engine()
print('✅ Database connection successful')
"
```

### 5. Channel Configuration
```bash
# Create channel configuration
mkdir -p mobasher/channels

cat > mobasher/channels/kuwait1.yaml << EOF
id: kuwait_news
name: Kuwait News Channel
description: Kuwait TV News Live Stream
input:
  url: https://kwtsplta.cdn.mangomolo.com/kb/smil:kb.stream.smil/chunklist.m3u8
  headers:
    Referer: "https://www.elahmad.com/?"
    User-Agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
output:
  audio:
    enabled: true
    format: wav
    sample_rate: 16000
    segment_seconds: 30
  video:
    enabled: true
    format: mp4
    resolution: "1280x720"
    bitrate: "2500k"
    segment_seconds: 60
  archive:
    enabled: true
    duration_minutes: 10
    quality: "720p"
    thumbnails: true
EOF

# Add channel to database
PYTHONPATH=. venv/bin/python -c "
from mobasher.storage.db import get_session, init_engine
from mobasher.storage.models import Channel
init_engine()

with next(get_session()) as db:
    channel = Channel(
        id='kuwait_news',
        name='Kuwait News Channel',
        description='Kuwait TV News Live Stream',
        url='https://kwtsplta.cdn.mangomolo.com/kb/smil:kb.stream.smil/chunklist.m3u8',
        headers={
            'Referer': 'https://www.elahmad.com/?',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        },
        active=True
    )
    db.merge(channel)
    db.commit()
    print('✅ Channel configuration added')
"
```

## Daily Operations

### Starting the System
```bash
# Navigate to project directory
cd /root/MediaView/mobasher

# Activate environment
source venv/bin/activate
source .env

# Start services in order
echo "🚀 Starting Mobasher staging environment..."

# 1. Start API server
PYTHONPATH=. venv/bin/python -m mobasher.cli.main api serve --host 0.0.0.0 --port 8010 &

# 2. Start main recorder
PYTHONPATH=. venv/bin/python -m mobasher.cli.main recorder start --config mobasher/channels/kuwait1.yaml &

# 3. Start archive recorder  
PYTHONPATH=. venv/bin/python -m mobasher.cli.main archive start --config mobasher/channels/kuwait1.yaml --duration-minutes 10 &

# 4. Start ASR worker (after upgrade to 4 vCPUs)
PYTHONPATH=. venv/bin/python -m mobasher.cli.main asr worker-start --workers 1 &

# 5. Start ASR scheduler (optional - auto-processes segments)
PYTHONPATH=. venv/bin/python -m mobasher.cli.main asr scheduler-start --interval 60 --lookback 15 &

# Check status
sleep 10
PYTHONPATH=. venv/bin/python -m mobasher.cli.main status
```

### Alternative: Combined Startup
```bash
# Start main + archive recorders together
PYTHONPATH=. venv/bin/python -m mobasher.cli.main recorder start-with-archive \
    --config mobasher/channels/kuwait1.yaml \
    --archive-duration-minutes 10 &
```

### Monitoring and Maintenance
```bash
# Check system status
mobasher status

# View recent segments
mobasher segments list --limit 10

# Check ASR queue
mobasher asr enqueue --dry-run --limit 10

# Monitor logs
tail -f /var/log/syslog | grep mobasher

# Check resource usage
htop
```

### Stopping the System
```bash
# Kill all processes
PYTHONPATH=. venv/bin/python -m mobasher.cli.main kill-the-minions

# Fresh reset (clears data and database)
PYTHONPATH=. venv/bin/python -m mobasher.cli.main freshreset --yes
```

## Testing Workflow

### 1. Basic Functionality Test
```bash
# Start API only
mobasher api serve --host 0.0.0.0 --port 8010 &

# Test API health
curl http://localhost:8010/health

# Check database connection
mobasher status
```

### 2. Recording Test
```bash
# Start recorder for 5 minutes
mobasher recorder start --config mobasher/channels/kuwait1.yaml --duration 300 &

# Monitor segment creation
watch -n 5 "mobasher status && ls -la data/kuwait_news/"

# Check segments in database
mobasher segments list --limit 5
```

### 3. Archive Test
```bash
# Start archive recorder for 15 minutes
mobasher archive start --config mobasher/channels/kuwait1.yaml --duration-minutes 10 --no-daemon

# Verify archive files and thumbnails
ls -la data/archive/kuwait_news/$(date +%Y-%m-%d)/

# Check database entries
PYTHONPATH=. venv/bin/python -c "
from mobasher.storage.db import get_session, init_engine
from mobasher.storage.models import Recording
init_engine()

with next(get_session()) as db:
    archives = db.query(Recording).filter(
        Recording.extra.op('->>')('type') == 'archive'
    ).all()
    print(f'Archive recordings: {len(archives)}')
    for rec in archives:
        print(f'  {rec.started_at} - {rec.extra.get(\"file_path\")}')
"
```

### 4. ASR Test (After 4 vCPU Upgrade)
```bash
# Start ASR worker
mobasher asr worker-start --workers 1 &

# Manually enqueue segments
mobasher asr enqueue --channel kuwait_news --limit 5

# Monitor processing
watch -n 10 "mobasher status && echo 'Transcripts:' && mobasher transcripts list --limit 3"
```

## Troubleshooting

### Common Issues
1. **Port already in use**: Check with `lsof -i :8010` and kill processes
2. **Database connection failed**: Verify PostgreSQL is running and credentials
3. **FFmpeg errors**: Check stream URL and network connectivity
4. **High CPU usage**: Monitor with `htop`, consider reducing quality settings

### Performance Optimization
```bash
# Check system resources
free -h
df -h
iostat -x 1 5

# Monitor process CPU usage
ps aux --sort=-%cpu | head -10

# Check ASR performance
curl http://localhost:9109/metrics | grep asr_
```

### Log Locations
- System logs: `/var/log/syslog`
- Application logs: Check terminal output or configure logging
- Database logs: `/var/log/postgresql/`
- Redis logs: `/var/log/redis/`

## Post-Upgrade Verification

After upgrading to 4 vCPU system:
1. ✅ All services start without errors
2. ✅ Recording creates segments (audio + video)
3. ✅ Archive creates 10-minute MP4s + thumbnails
4. ✅ Database entries created for archives
5. ✅ ASR worker processes segments successfully
6. ✅ System load stays below 80%
7. ✅ Memory usage under 6GB

## Success Metrics
- **Recording**: Continuous segment creation every 30s (audio) / 60s (video)
- **Archive**: 10-minute MP4 files with thumbnails every 10 minutes
- **Database**: Archive entries with full metadata
- **ASR**: 2-3 segments processed per minute
- **System**: CPU usage <80%, memory usage <6GB
- **Stability**: 24+ hour continuous operation
