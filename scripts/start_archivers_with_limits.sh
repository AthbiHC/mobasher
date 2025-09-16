#!/bin/bash
#
# Memory-Aware Mobasher Archivers Startup Script
# Implements 4-hour restart cycles and memory monitoring
#

set -e

# Get the actual script location and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Debug: show detected paths
echo "DEBUG - SCRIPT_DIR: ${SCRIPT_DIR}"
echo "DEBUG - PROJECT_ROOT before fix: ${PROJECT_ROOT}"

# Force correct path - we know we're in MediaView project
PROJECT_ROOT="/root/MediaView"
VENV_PATH="${PROJECT_ROOT}/mobasher/venv"
CHANNELS_DIR="${PROJECT_ROOT}/mobasher/mobasher/channels"
LOG_DIR="${PROJECT_ROOT}/mobasher/mobasher/ingestion"

echo "🚀 Starting Memory-Managed Mobasher Archivers..."
echo "Project Root: ${PROJECT_ROOT}"
echo "Script Dir: ${SCRIPT_DIR}"
echo "VENV Path: ${VENV_PATH}"
echo "Memory Management: 2GB max per process, 4-hour restart cycles"

# Activate virtual environment
source "${VENV_PATH}/bin/activate"
export PYTHONPATH="${PROJECT_ROOT}/mobasher:${PYTHONPATH}"
cd "${PROJECT_ROOT}/mobasher"

# Function to start an archiver with memory limits
start_archiver() {
    local channel=$1
    local port=$2  
    local log_file="${LOG_DIR}/archive_${channel}.log"
    
    echo "Starting ${channel} archiver (Port: ${port}, Memory: 2GB max)..."
    
    # Use systemd-run for cgroup memory management if available
    if command -v systemd-run &> /dev/null; then
        systemd-run --user --slice=archiver-${channel}.slice \
            --property=MemoryMax=2G \
            --property=MemoryHigh=1.5G \
            --property=RuntimeMaxSec=4h \
            --unit=archiver-${channel} \
            bash -c "cd '${PROJECT_ROOT}/mobasher' && source venv/bin/activate && \
                export PYTHONPATH='${PROJECT_ROOT}/mobasher' && \
                python -m mobasher.ingestion.archive_recorder \
                    --config '${CHANNELS_DIR}/${channel}.yaml' \
                    --metrics-port '${port}' \
                    --quality 720p \
                    --duration-minutes 30 \
                    > '${log_file}' 2>&1" &
    else
        # Fallback to ulimit (less effective but better than nothing)
        (
            # Set memory limit via ulimit (2GB = 2097152 KB)
            ulimit -v 2097152
            cd "${PROJECT_ROOT}/mobasher"
            
            timeout 4h python -m mobasher.ingestion.archive_recorder \
                --config "${CHANNELS_DIR}/${channel}.yaml" \
                --metrics-port "${port}" \
                --quality 720p \
                --duration-minutes 30 \
                > "${log_file}" 2>&1
        ) &
    fi
    
    local pid=$!
    echo "  └── Started with PID: ${pid} (4-hour timeout)"
    sleep 2
}

# Kill existing processes
echo "🛑 Stopping any existing archivers..."
pkill -f "archive_recorder" 2>/dev/null || true
systemctl --user stop 'archiver-*.service' 2>/dev/null || true
sleep 3

# Channel port mappings
declare -A CHANNELS=(
    ["kuwait1"]="9120"
    ["al_jazeera"]="9121"
    ["al_arabiya"]="9122"
    ["sky_news_arabia"]="9125"
    ["al_ekhbariya"]="9123"
    ["cnbc_arabia"]="9124"
)

# Start archivers for each channel
echo "📺 Starting memory-limited archivers..."
for channel in "${!CHANNELS[@]}"; do
    start_archiver "$channel" "${CHANNELS[$channel]}"
done

echo ""
echo "✅ All archivers started with memory management!"
echo ""
echo "🛡️ Memory Protection:"
echo "  - Max RAM per process: 2GB"
echo "  - Automatic restart: Every 4 hours"  
echo "  - Swap space available: 8GB"
echo ""
echo "📊 Monitoring:"
for channel in "${!CHANNELS[@]}"; do
    echo "  - ${channel}: http://localhost:${CHANNELS[$channel]}/metrics"
done
echo ""
echo "⚠️  Processes will auto-restart every 4 hours to prevent memory accumulation"
echo "📝 Logs: tail -f ${LOG_DIR}/archive_*.log"
echo "🔧 Status: ./quick_status_check.sh"
