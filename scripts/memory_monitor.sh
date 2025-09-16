#!/bin/bash
#
# Memory Usage Monitor for Mobasher Processes
# Alerts when processes approach memory limits
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALERT_THRESHOLD_MB=1536  # Alert at 1.5GB (before 2GB limit)
LOG_FILE="${SCRIPT_DIR}/../memory_alerts.log"

echo "🧠 Memory Monitor - $(date)" | tee -a "$LOG_FILE"

# Function to check process memory and alert
check_process_memory() {
    local process_pattern=$1
    local process_name=$2
    
    # Get memory usage in MB for matching processes
    local memory_info=$(ps aux | grep -E "$process_pattern" | grep -v grep | awk '{print $2, $6/1024, $11}' 2>/dev/null)
    
    if [ -n "$memory_info" ]; then
        echo "$memory_info" | while read pid memory_mb command; do
            memory_mb=${memory_mb%.*} # Remove decimal places
            
            if (( memory_mb > ALERT_THRESHOLD_MB )); then
                local alert="⚠️  HIGH MEMORY: $process_name (PID: $pid) using ${memory_mb}MB (>${ALERT_THRESHOLD_MB}MB threshold)"
                echo "$alert" | tee -a "$LOG_FILE"
                
                # Optional: Restart the process before it hits OOM
                echo "🔄 Consider restarting PID $pid to prevent OOM" | tee -a "$LOG_FILE"
            else
                echo "✅ $process_name (PID: $pid): ${memory_mb}MB memory usage OK"
            fi
        done
    else
        echo "ℹ️  No $process_name processes found"
    fi
}

echo "Memory Usage Report:"
echo "===================="

# Check different process types
check_process_memory "archive_recorder" "Archiver"
check_process_memory "recorder\.py" "Recorder" 
check_process_memory "ffmpeg.*archive" "Archive FFmpeg"
check_process_memory "ffmpeg.*video" "Video FFmpeg"
check_process_memory "ffmpeg.*audio" "Audio FFmpeg"

# System memory overview
echo ""
echo "System Memory Status:"
free -h

echo ""
echo "Swap Usage:"
swapon --show

echo ""
echo "Top Memory Consumers:"
ps aux --sort=-%mem | head -10

# Check for recent OOM kills
if dmesg | grep -i "killed process" | tail -1 | grep -q "$(date '+%b %d')"; then
    echo "" | tee -a "$LOG_FILE"
    echo "🚨 RECENT OOM KILL DETECTED TODAY!" | tee -a "$LOG_FILE"
    dmesg | grep -i "killed process" | tail -5 | tee -a "$LOG_FILE"
fi

echo "$(date): Memory check completed" >> "$LOG_FILE"
