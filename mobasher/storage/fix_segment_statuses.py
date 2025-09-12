#!/usr/bin/env python3
"""
Fix segment pipeline statuses based on available media.

Audio-only segments should have vision_status = 'completed'
Video-only segments should have asr_status = 'completed'
"""

from mobasher.storage.db import get_session, init_engine
from mobasher.storage.models import Segment


def fix_segment_statuses(dry_run: bool = True) -> None:
    """Fix pipeline statuses for existing segments."""
    init_engine()
    
    with next(get_session()) as db:
        segments = db.query(Segment).all()
        
        audio_only_fixed = 0
        video_only_fixed = 0
        
        for seg in segments:
            changed = False
            
            # Audio-only segments: should have vision_status = 'completed'
            if seg.audio_path and not seg.video_path:
                if seg.vision_status == 'pending':
                    if not dry_run:
                        seg.vision_status = 'completed'
                    audio_only_fixed += 1
                    changed = True
            
            # Video-only segments: should have asr_status = 'completed'  
            elif seg.video_path and not seg.audio_path:
                if seg.asr_status == 'pending':
                    if not dry_run:
                        seg.asr_status = 'completed'
                    video_only_fixed += 1
                    changed = True
            
            if changed and not dry_run:
                db.add(seg)
        
        if not dry_run:
            db.commit()
        
        print(f"{'DRY RUN: ' if dry_run else ''}Fixed {audio_only_fixed} audio-only segments (vision_status)")
        print(f"{'DRY RUN: ' if dry_run else ''}Fixed {video_only_fixed} video-only segments (asr_status)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix segment pipeline statuses")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()
    
    fix_segment_statuses(dry_run=not args.apply)
