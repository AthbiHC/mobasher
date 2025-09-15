#!/usr/bin/env python3
"""
Mobasher Performance Monitor
Tracks recording, archiving, and ASR processing performance over time.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add mobasher to path
sys.path.insert(0, '/root/MediaView/mobasher')

from mobasher.storage.db import get_session, init_engine
from mobasher.storage.models import Segment, Transcript, Recording

def get_current_metrics():
    """Get current system metrics."""
    init_engine()
    with next(get_session()) as db:
        # Segments
        total_segments = db.query(Segment).count()
        audio_segments = db.query(Segment).filter(Segment.audio_path.isnot(None)).count()
        
        # ASR Status
        pending = db.query(Segment).filter(Segment.asr_status == 'pending').count()
        queued = db.query(Segment).filter(Segment.asr_status == 'queued').count()
        processing = db.query(Segment).filter(Segment.asr_status == 'processing').count()
        completed = db.query(Segment).filter(Segment.asr_status == 'completed').count()
        failed = db.query(Segment).filter(Segment.asr_status == 'failed').count()
        
        # Transcripts
        transcripts = db.query(Transcript).count()
        
        # Recordings
        recordings = db.query(Recording).all()
        archive_recordings = len([r for r in recordings if r.extra and r.extra.get('type') == 'archive'])
        main_recordings = len(recordings) - archive_recordings
        
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'segments': {
                'total': total_segments,
                'audio': audio_segments,
                'video_only': total_segments - audio_segments
            },
            'asr_status': {
                'pending': pending,
                'queued': queued,
                'processing': processing,
                'completed': completed,
                'failed': failed,
                'completion_rate': round(completed / audio_segments * 100, 1) if audio_segments > 0 else 0
            },
            'transcripts': transcripts,
            'recordings': {
                'total': len(recordings),
                'main': main_recordings,
                'archive': archive_recordings
            }
        }

def load_baseline():
    """Load baseline metrics."""
    try:
        with open('/tmp/mobasher_baseline.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def calculate_performance(baseline, current):
    """Calculate performance metrics between baseline and current."""
    if not baseline:
        return {}
    
    baseline_time = datetime.fromisoformat(baseline['timestamp'])
    current_time = datetime.fromisoformat(current['timestamp'])
    elapsed_minutes = (current_time - baseline_time).total_seconds() / 60
    
    # Calculate changes
    segments_delta = current['segments']['total'] - baseline['segments']['total']
    audio_segments_delta = current['segments']['audio'] - baseline['segments']['audio']
    transcripts_delta = current['transcripts'] - baseline['transcripts']
    archive_delta = current['recordings']['archive'] - baseline['recordings']['archive']
    completed_delta = current['asr_status']['completed'] - baseline['asr_status']['completed']
    
    # Calculate rates (per minute)
    segment_rate = segments_delta / elapsed_minutes if elapsed_minutes > 0 else 0
    transcript_rate = transcripts_delta / elapsed_minutes if elapsed_minutes > 0 else 0
    archive_rate = archive_delta / elapsed_minutes if elapsed_minutes > 0 else 0
    asr_completion_rate = completed_delta / elapsed_minutes if elapsed_minutes > 0 else 0
    
    return {
        'elapsed_minutes': round(elapsed_minutes, 1),
        'deltas': {
            'segments': segments_delta,
            'audio_segments': audio_segments_delta,
            'transcripts': transcripts_delta,
            'archive_recordings': archive_delta,
            'asr_completed': completed_delta
        },
        'rates_per_minute': {
            'segments': round(segment_rate, 2),
            'transcripts': round(transcript_rate, 2),
            'archive_recordings': round(archive_rate, 2),
            'asr_completions': round(asr_completion_rate, 2)
        }
    }

def get_system_resources():
    """Get current system resource usage."""
    try:
        # Get ASR worker processes
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        asr_processes = [line for line in result.stdout.split('\n') if 'asr_worker' in line and 'celery' in line]
        
        total_cpu = 0
        total_memory_mb = 0
        worker_count = 0
        
        for proc in asr_processes:
            parts = proc.split()
            if len(parts) >= 6:
                try:
                    cpu = float(parts[2])
                    memory_kb = float(parts[5])
                    total_cpu += cpu
                    total_memory_mb += memory_kb / 1024
                    worker_count += 1
                except (ValueError, IndexError):
                    pass
        
        return {
            'asr_workers': worker_count,
            'total_cpu_percent': round(total_cpu, 1),
            'total_memory_gb': round(total_memory_mb / 1024, 1)
        }
    except:
        return {'asr_workers': 0, 'total_cpu_percent': 0, 'total_memory_gb': 0}

def print_monitoring_report():
    """Print comprehensive monitoring report."""
    current = get_current_metrics()
    baseline = load_baseline()
    performance = calculate_performance(baseline, current)
    resources = get_system_resources()
    
    print(f"\n🔍 MOBASHER PERFORMANCE MONITOR")
    print(f"{'='*50}")
    print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S UTC')}")
    
    if performance:
        print(f"📈 Elapsed: {performance['elapsed_minutes']:.1f} minutes")
    
    # Current Status
    print(f"\n📊 CURRENT STATUS:")
    print(f"   Segments: {current['segments']['total']} (Audio: {current['segments']['audio']}, Video: {current['segments']['video_only']})")
    print(f"   Recordings: {current['recordings']['total']} (Main: {current['recordings']['main']}, Archive: {current['recordings']['archive']})")
    print(f"   Transcripts: {current['transcripts']}")
    
    # ASR Pipeline
    print(f"\n⚡ ASR PIPELINE:")
    asr = current['asr_status']
    print(f"   Pending: {asr['pending']}, Queued: {asr['queued']}, Processing: {asr['processing']}")
    print(f"   Completed: {asr['completed']}, Failed: {asr['failed']}")
    print(f"   Completion Rate: {asr['completion_rate']}%")
    
    # Performance Metrics
    if performance and performance['elapsed_minutes'] > 0:
        print(f"\n🚀 PERFORMANCE (since baseline):")
        deltas = performance['deltas']
        rates = performance['rates_per_minute']
        print(f"   New Segments: +{deltas['segments']} ({rates['segments']}/min)")
        print(f"   New Transcripts: +{deltas['transcripts']} ({rates['transcripts']}/min)")
        print(f"   New Archives: +{deltas['archive_recordings']} ({rates['archive_recordings']}/min)")
        print(f"   ASR Completions: +{deltas['asr_completed']} ({rates['asr_completions']}/min)")
    
    # System Resources
    print(f"\n💻 SYSTEM RESOURCES:")
    print(f"   ASR Workers: {resources['asr_workers']}")
    print(f"   Total CPU: {resources['total_cpu_percent']}%")
    print(f"   ASR Memory: {resources['total_memory_gb']} GB")
    
    # Queue Analysis
    total_workload = asr['pending'] + asr['queued'] + asr['processing']
    if total_workload > 0 and resources['asr_workers'] > 0:
        eta_minutes = total_workload / (resources['asr_workers'] * 0.5)  # Assume 0.5 segments/worker/minute
        print(f"\n⏱️  QUEUE ANALYSIS:")
        print(f"   Total Workload: {total_workload} segments")
        print(f"   ETA to Clear: ~{eta_minutes:.1f} minutes")
    
    print(f"\n{'='*50}")

if __name__ == "__main__":
    print_monitoring_report()
