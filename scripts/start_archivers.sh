#!/bin/bash
#
# Mobasher Archivers Startup Script
# Fixes Python environment issues by setting correct PYTHONPATH
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
CHANNELS_DIR="${PROJECT_ROOT}/mobasher/channels"
LOG_DIR="${PROJECT_ROOT}/mobasher/ingestion"

echo "🚀 Starting Mobasher Archivers with fixed Python environment..."
echo "Project Root: ${PROJECT_ROOT}"
echo "Virtual Environment: ${VENV_PATH}"

# Activate virtual environment
source "${VENV_PATH}/bin/activate"

# Set correct PYTHONPATH so mobasher module can be found
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Change to project directory
cd "${PROJECT_ROOT}"

# Function to start an archiver
start_archiver() {
    local channel=$1
    local port=$2
    local log_file="${LOG_DIR}/archive_${channel}.log"
    
    echo "Starting ${channel} archiver on port ${port}..."
    
    nohup python -m mobasher.ingestion.archive_recorder \
        --config "${CHANNELS_DIR}/${channel}.yaml" \
        --metrics-port "${port}" \
        --quality 720p \
        --duration-minutes 30 \
        > "${log_file}" 2>&1 &
    
    local pid=$!
    echo "  └── Started with PID: ${pid}"
    sleep 1
}

# Kill any existing archiver processes
echo "🛑 Stopping any existing archivers..."
pkill -f "archive_recorder" 2>/dev/null || true
sleep 2

# Start archivers for each channel
echo "📺 Starting channel archivers..."
start_archiver "kuwait1" 9120
start_archiver "al_jazeera" 9121  
start_archiver "al_arabiya" 9122
start_archiver "sky_news_arabia" 9125
start_archiver "al_ekhbariya" 9123
start_archiver "cnbc_arabia" 9124

echo ""
echo "✅ All archivers started successfully!"
echo ""
echo "📊 Metrics endpoints:"
echo "  - Kuwait News:      http://localhost:9120/metrics"
echo "  - Al Jazeera:       http://localhost:9121/metrics" 
echo "  - Al Arabiya:       http://localhost:9122/metrics"
echo "  - Sky News Arabia:  http://localhost:9125/metrics"
echo "  - Al Ekhbariya:     http://localhost:9123/metrics"
echo "  - CNBC Arabia:      http://localhost:9124/metrics"
echo ""
echo "📋 To check status:"
echo "  ps aux | grep archive_recorder"
echo "  python -m mobasher.cli.main status"
echo ""
echo "📝 Log files in: ${LOG_DIR}/"
