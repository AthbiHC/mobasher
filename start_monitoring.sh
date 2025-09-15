#!/bin/bash
# Continuous Mobasher Performance Monitoring Script

cd /root/MediaView/mobasher

echo "🔍 Starting Mobasher Performance Monitor"
echo "Monitoring every 3 minutes..."
echo "Press Ctrl+C to stop"
echo "========================================"

while true; do
    echo "$(date '+%Y-%m-%d %H:%M:%S'): Running performance check..." | tee -a monitor.log
    PYTHONPATH=. venv/bin/python monitor_performance.py | tee -a monitor.log
    echo "" | tee -a monitor.log
    
    # Wait 3 minutes (180 seconds)
    sleep 180
done
