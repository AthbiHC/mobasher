#!/bin/bash
#
# Memory-Aware Mobasher Recorders Startup Script
# Implements memory limits and monitoring
#

set -e

PROJECT_ROOT="/root/MediaView"
VENV_PATH="${PROJECT_ROOT}/mobasher/venv"
CHANNELS_DIR="${PROJECT_ROOT}/mobasher/mobasher/channels"
LOG_DIR="${PROJECT_ROOT}/mobasher/mobasher/ingestion"

echo "🚀 Starting Memory-Managed Mobasher Recorders..."
echo "Project Root: ${PROJECT_ROOT}"
echo "Memory Management: 1.5GB max per process"

# Activate virtual environment
source "${VENV_PATH}/bin/activate"
export PYTHONPATH="${PROJECT_ROOT}/mobasher:${PYTHONPATH}"
cd "${PROJECT_ROOT}/mobasher"

# Function to start a recorder with memory limits
start_recorder() {
    local channel=$1
    local port=$2
    local log_file="${LOG_DIR}/recorder_${channel}.log"
    
    echo "Starting ${channel} recorder (Port: ${port}, Memory: 1.5GB max)..."
    
    # Use systemd-run for cgroup memory management if available
    if command -v systemd-run &> /dev/null; then
        systemd-run --user --slice=recorder-${channel}.slice \
            --property=MemoryMax=1536M \
            --property=MemoryHigh=1024M \
            --unit=recorder-${channel} \
            bash -c "cd '${PROJECT_ROOT}/mobasher' && source venv/bin/activate && \
                export PYTHONPATH='${PROJECT_ROOT}/mobasher' && \
                python recorder.py \
                    --config '${CHANNELS_DIR}/${channel}.yaml' \
                    --heartbeat 15 \
                    --metrics-port '${port}' \
                    > '${log_file}' 2>&1" &
    else
        # Fallback to ulimit (less effective but better than nothing)
        (
            # Set memory limit via ulimit (1.5GB = 1572864 KB)
            ulimit -v 1572864
            cd "${PROJECT_ROOT}/mobasher"
            
            python recorder.py \
                --config "${CHANNELS_DIR}/${channel}.yaml" \
                --heartbeat 15 \
                --metrics-port "${port}" \
                > "${log_file}" 2>&1
        ) &
    fi
    
    local pid=$!
    echo "  └── Started with PID: ${pid}"
    sleep 3
}

# Kill existing processes
echo "🛑 Stopping any existing recorders..."
pkill -f "recorder.py" 2>/dev/null || true
systemctl --user stop 'recorder-*.service' 2>/dev/null || true
sleep 3

# Channel port mappings (9108-9113 based on previous status)
declare -A CHANNELS=(
    ["kuwait1"]="9108"
    ["al_jazeera"]="9109" 
    ["al_arabiya"]="9110"
    ["sky_news_arabia"]="9113"
    ["al_ekhbariya"]="9111"
    ["cnbc_arabia"]="9112"
)

# Start recorders for each channel
echo "📺 Starting memory-limited recorders..."
for channel in "${!CHANNELS[@]}"; do
    start_recorder "$channel" "${CHANNELS[$channel]}"
done

echo ""
echo "✅ All recorders started with memory management!"
echo ""
echo "🛡️ Memory Protection:"
echo "  - Max RAM per process: 1.5GB"
echo "  - High water mark: 1GB"
echo "  - Process monitoring: Active"
echo ""
echo "📊 Monitoring:"
for channel in "${!CHANNELS[@]}"; do
    echo "  - ${channel}: http://localhost:${CHANNELS[$channel]}/metrics"
done
echo ""
echo "📝 Logs: tail -f ${LOG_DIR}/recorder_*.log"
echo "🔧 Combined Status: ./scripts/memory_monitor.sh"