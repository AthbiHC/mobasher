"""
Mobasher Archive Recorder

Creates hour-aligned MP4 archives per channel with optional thumbnails.

Output path:
  data/archive/<channel_id>/<YYYY-MM-DD>/<channel_id>-YYYY-MM-DD-HH-00-00.mp4
Thumbnail path:
  data/archive/<channel_id>/<YYYY-MM-DD>/<channel_id>-YYYY-MM-DD-HH-00-00-thumb.jpg
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

import yaml

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
except Exception:  # pragma: no cover - metrics are optional
    # Minimal shims if prometheus_client is unavailable
    class _N:
        def labels(self, **kwargs):  # type: ignore
            return self
        def inc(self, *a, **k):
            pass
        def set(self, *a, **k):
            pass
        def observe(self, *a, **k):
            pass
    def start_http_server(port: int) -> None:  # type: ignore
        return
    Counter = Gauge = Histogram = _N  # type: ignore


logger = logging.getLogger(__name__)


def _build_header_string(headers: Dict[str, str]) -> str:
    if not headers:
        return ""
    return "\r\n".join([f"{k}: {v}" for k, v in headers.items()]) + "\r\n"


def _today_folder() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class ArchiveOptions:
    mode: str  # "copy" | "encode"
    quality: str  # example: "720p"
    thumbs: bool
    thumb_format: str  # "jpg" | "png"
    thumb_height: int
    thumb_offset_sec: int
    segment_seconds: int = 600   # 10 minutes for easier monitoring


class ArchiveRecorder:
    def __init__(self, channel_cfg: Dict, data_root: Path, opts: ArchiveOptions) -> None:
        self.cfg = channel_cfg
        self.channel_id: str = channel_cfg["id"]
        self.data_root = data_root.resolve()
        self.opts = opts

        # storage layout
        self.archive_dir_base = self.data_root / "archive" / self.channel_id
        self.current_date_dir = self.archive_dir_base / _today_folder()
        self.current_date_dir.mkdir(parents=True, exist_ok=True)

        # metrics
        self.metrics_running = Gauge("mobasher_archive_running", "Archive running (1/0)", ["channel_id"])  # type: ignore
        self.metrics_segments = Counter("mobasher_archive_segments_total", "Archive files completed", ["channel_id"])  # type: ignore
        self.metrics_thumbs = Counter("mobasher_archive_thumbnails_total", "Archive thumbnails created", ["channel_id"])  # type: ignore
        self.metrics_errors = Counter("mobasher_archive_errors_total", "Archive errors", ["channel_id"])  # type: ignore
        self.metrics_last_cut = Gauge("mobasher_archive_last_cut_timestamp", "Unix ts of last archive cut", ["channel_id"])  # type: ignore
        self.metrics_restarts = Counter("mobasher_archive_restarts_total", "Archive process restarts", ["channel_id"])  # type: ignore

        try:
            self.metrics_running.labels(channel_id=self.channel_id).set(0)
        except Exception:
            pass
        
        # Process monitoring
        self.process: Optional[asyncio.subprocess.Process] = None
        self.restart_count = 0
        self.last_restart = datetime.now(timezone.utc)
        self.max_restarts_per_hour = 5
        
        # Database tracking
        self.current_recording_id: Optional[str] = None
        self.recording_start_time: Optional[datetime] = None

    def _ffmpeg_base(self) -> list[str]:
        stream_url = self.cfg["input"]["url"]
        headers = self.cfg["input"].get("headers", {})
        header_string = _build_header_string(headers)
        cmd: list[str] = [
            "ffmpeg", "-nostdin", "-loglevel", "warning",  # More verbose for debugging
            "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "30",
            "-reconnect_at_eof", "1", "-timeout", "10000000",  # 10 second timeout
            "-user_agent", headers.get("User-Agent", "Mobasher/1.0"),
        ]
        if header_string:
            cmd += ["-headers", header_string]
        cmd += ["-i", stream_url]
        return cmd

    def _ffmpeg_output_pattern(self) -> str:
        # data/archive/<channel_id>/%Y-%m-%d/<channel_id>-%Y-%m-%d-%H%M%S.mp4
        # Changed from hour-aligned to minute-second for 10-minute segments
        return str(self.archive_dir_base / "%Y-%m-%d" / f"{self.channel_id}-%Y-%m-%d-%H%M%S.mp4")

    def _ffmpeg_command(self) -> list[str]:
        cmd = self._ffmpeg_base()
        # mapping
        cmd += ["-map", "0:v:0", "-map", "0:a:0"]
        if self.opts.mode == "copy":
            cmd += ["-c", "copy", "-movflags", "+faststart"]
        else:
            # encode path; prefer hardware on macOS
            import platform
            if platform.system().lower() == "darwin":
                cmd += ["-c:v", "h264_videotoolbox", "-realtime", "true", "-pix_fmt", "yuv420p"]
            else:
                cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
            # conservative 720p defaults; could consult cfg["video"]["qualities"][self.opts.quality]
            cmd += ["-b:v", "3500k", "-r", "25"]
            cmd += ["-c:a", "aac", "-b:a", "128k"]

        # time-based segmenting
        cmd += [
            "-f", "segment",
            "-segment_atclocktime", "1",
            "-segment_time", str(self.opts.segment_seconds),
            "-reset_timestamps", "1",
            "-strftime", "1",
            self._ffmpeg_output_pattern(),
        ]
        return cmd

    async def _ensure_today_dir(self) -> None:
        cur = self.archive_dir_base / _today_folder()
        if cur != self.current_date_dir:
            self.current_date_dir = cur
            self.current_date_dir.mkdir(parents=True, exist_ok=True)

    async def _spawn_ffmpeg(self) -> asyncio.subprocess.Process:
        cmd = self._ffmpeg_command()
        logger.info("Starting archive ffmpeg | %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,  # Capture for debugging
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )
        self.process = proc  # Store for monitoring
        return proc
    
    async def _monitor_process(self) -> None:
        """Monitor FFmpeg process and restart if it fails."""
        if not self.process:
            return
            
        now = datetime.now(timezone.utc)
        
        # Reset restart counter every hour
        if (now - self.last_restart).total_seconds() > 3600:
            self.restart_count = 0
            self.last_restart = now
        
        # Check if process has terminated
        if self.process.returncode is not None:
            logger.warning(f"Archive process terminated with code {self.process.returncode}")
            
            try:
                self.metrics_errors.labels(channel_id=self.channel_id).inc()
            except Exception:
                pass
            
            if self.restart_count < self.max_restarts_per_hour:
                logger.info("Restarting archive process...")
                await self._restart_process()
            else:
                logger.error("Archive restart limit reached, stopping")
                return False
        
        return True
    
    async def _restart_process(self) -> None:
        """Restart the archive FFmpeg process."""
        try:
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
                except Exception:
                    pass
            
            # Restart the process
            self.process = await self._spawn_ffmpeg()
            self.restart_count += 1
            
            try:
                self.metrics_restarts.labels(channel_id=self.channel_id).inc()
            except Exception:
                pass
            
            logger.info(f"Archive process restarted (attempt {self.restart_count})")
            
        except Exception as e:
            logger.error(f"Failed to restart archive process: {e}")
            try:
                self.metrics_errors.labels(channel_id=self.channel_id).inc()
            except Exception:
                pass

    async def _thumbnail_worker(self) -> None:
        """Periodically create thumbnails for completed files (no thumb yet)."""
        while True:
            try:
                await self._ensure_today_dir()
                for mp4 in sorted(self.current_date_dir.glob("*.mp4")):
                    thumb = mp4.with_name(mp4.stem + "-thumb." + self.opts.thumb_format)
                    if thumb.exists():
                        continue
                    # Heuristic: only thumb files older than 30s to avoid partials
                    try:
                        age = time.time() - mp4.stat().st_mtime
                    except FileNotFoundError:
                        continue
                    if age < 30:
                        continue
                    await self._extract_thumbnail(mp4, thumb)
                    try:
                        self.metrics_thumbs.labels(channel_id=self.channel_id).inc()  # type: ignore
                    except Exception:
                        pass
            except Exception as e:  # pragma: no cover
                logger.warning("thumbnail worker error: %s", e)
            await asyncio.sleep(15)

    async def _extract_thumbnail(self, mp4_path: Path, out_path: Path) -> None:
        """Extract intelligent thumbnail from video file."""
        try:
            # Get video duration first
            duration = await self._get_video_duration(mp4_path)
            if not duration:
                duration = 600  # Default 10 minutes
            
            # Smart timing: avoid first/last 10 seconds, prefer middle section
            avoid_start = min(10, duration * 0.1)  # Avoid first 10 seconds or 10% 
            avoid_end = min(10, duration * 0.1)    # Avoid last 10 seconds or 10%
            usable_duration = duration - avoid_start - avoid_end
            
            if usable_duration > 0:
                # Take thumbnail from middle of usable section
                thumbnail_time = avoid_start + (usable_duration / 2)
            else:
                # Fallback to simple middle
                thumbnail_time = duration / 2
            
            vf = f"scale=-2:{self.opts.thumb_height}:flags=lanczos"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(int(thumbnail_time)),
                "-i", str(mp4_path),
                "-frames:v", "1",
                "-vf", vf,
            ]
            if self.opts.thumb_format.lower() == "jpg":
                cmd += ["-q:v", "2"]
            cmd += [str(out_path)]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.DEVNULL, 
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
            
            if proc.returncode == 0:
                logger.debug(f"Created thumbnail at {int(thumbnail_time)}s for {mp4_path.name}")
            else:
                logger.warning(f"Thumbnail creation failed for {mp4_path.name}")
                
        except Exception as e:
            logger.warning(f"Thumbnail extraction error for {mp4_path.name}: {e}")
    
    async def _get_video_duration(self, video_path: Path) -> Optional[float]:
        """Get video duration in seconds using ffprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "compact=print_section=0:nokey=1:escape=csv",
                "-show_entries", "format=duration", str(video_path)
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            if proc.returncode == 0 and stdout:
                duration_str = stdout.decode().strip()
                return float(duration_str)
        except (asyncio.TimeoutError, ValueError, Exception):
            pass
        
        return None

    @asynccontextmanager
    async def _db_session(self):
        """Async context manager for database sessions."""
        try:
            # Import here to avoid circular imports
            from mobasher.storage.db import get_session
            with next(get_session()) as session:
                yield session
        except Exception as e:
            logger.warning(f"Database session error: {e}")
            yield None

    async def _create_archive_recording(self, start_time: datetime, mp4_path: Path, thumbnail_path: Optional[Path] = None) -> None:
        """Create a database entry for the archive file."""
        try:
            from mobasher.storage.models import Recording, Channel
            
            # Generate recording ID
            recording_id = str(uuid4())
            
            # Get file info
            file_size = mp4_path.stat().st_size if mp4_path.exists() else 0
            duration = await self._get_video_duration(mp4_path) or self.opts.segment_seconds
            
            # Prepare metadata
            metadata = {
                "type": "archive",
                "file_path": str(mp4_path),
                "file_size_bytes": file_size,
                "duration_seconds": int(duration),
                "segment_duration_config": self.opts.segment_seconds,
                "mode": self.opts.mode,
                "quality": self.opts.quality,
            }
            
            if thumbnail_path and thumbnail_path.exists():
                metadata["thumbnail_path"] = str(thumbnail_path)
                metadata["thumbnail_size_bytes"] = thumbnail_path.stat().st_size
            
            async with self._db_session() as session:
                if session is None:
                    return
                    
                # Ensure channel exists
                channel = session.get(Channel, self.channel_id)
                if channel is None:
                    input_cfg = self.cfg.get('input', {})
                    channel = Channel(
                        id=self.channel_id,
                        name=self.cfg.get('name', self.channel_id),
                        description=self.cfg.get('description'),
                        url=input_cfg.get('url', ''),
                        headers=input_cfg.get('headers', {}),
                        active=True,
                    )
                    session.add(channel)
                    session.flush()
                
                # Create archive recording entry
                end_time = start_time.replace(second=0, microsecond=0) + timedelta(seconds=self.opts.segment_seconds)
                
                recording = Recording(
                    id=recording_id,
                    channel_id=self.channel_id,
                    started_at=start_time,
                    ended_at=end_time,
                    status='completed',
                    extra=metadata,
                )
                
                session.add(recording)
                session.commit()
                
                logger.info(f"Created archive recording entry: {recording_id} for {mp4_path.name}")
                
        except Exception as e:
            logger.error(f"Failed to create archive recording entry: {e}")

    async def _track_completed_files(self) -> None:
        """Check for completed archive files and create database entries."""
        try:
            await self._ensure_today_dir()
            
            # Look for MP4 files without corresponding database entries
            for mp4_path in sorted(self.current_date_dir.glob("*.mp4")):
                # Skip files that are too new (might still be writing)
                try:
                    age = time.time() - mp4_path.stat().st_mtime
                    if age < 60:  # Skip files newer than 1 minute
                        continue
                except (OSError, FileNotFoundError):
                    continue
                
                # Check if we already have a database entry for this file
                # We'll use a simple file-based tracking for now
                marker_file = mp4_path.with_suffix('.db_tracked')
                if marker_file.exists():
                    continue
                
                # Extract start time from filename
                # Format: kuwait_news-2025-09-12-144333.mp4
                try:
                    filename = mp4_path.stem
                    # Extract timestamp part after last dash
                    parts = filename.split('-')
                    if len(parts) >= 4:
                        date_part = '-'.join(parts[-3:-1])  # YYYY-MM-DD
                        time_part = parts[-1]  # HHMMSS
                        
                        # Parse datetime
                        datetime_str = f"{date_part} {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                        start_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        
                        # Find corresponding thumbnail
                        thumbnail_path = mp4_path.with_name(mp4_path.stem + "-thumb.jpg")
                        if not thumbnail_path.exists():
                            thumbnail_path = None
                        
                        # Create database entry
                        await self._create_archive_recording(start_time, mp4_path, thumbnail_path)
                        
                        # Mark as tracked
                        marker_file.touch()
                        
                except Exception as e:
                    logger.warning(f"Could not parse timestamp from {mp4_path.name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Error tracking completed files: {e}")

    async def run(self) -> None:
        try:
            self.metrics_running.labels(channel_id=self.channel_id).set(1)  # type: ignore
        except Exception:
            pass
        
        thumb_task: Optional[asyncio.Task] = None
        monitor_task: Optional[asyncio.Task] = None
        db_task: Optional[asyncio.Task] = None
        
        try:
            if self.opts.thumbs:
                thumb_task = asyncio.create_task(self._thumbnail_worker())
            
            # Start database tracking task
            async def db_tracking_loop():
                while True:
                    await self._track_completed_files()
                    await asyncio.sleep(30)  # Check every 30 seconds
            
            db_task = asyncio.create_task(db_tracking_loop())
            
            proc = await self._spawn_ffmpeg()
            
            # Start process monitoring
            async def monitor_loop():
                while True:
                    should_continue = await self._monitor_process()
                    if not should_continue:
                        break
                    await asyncio.sleep(10)  # Check every 10 seconds
            
            monitor_task = asyncio.create_task(monitor_loop())
            
            # Wait for process to complete or monitoring to stop it
            await proc.wait()
            
        finally:
            try:
                self.metrics_running.labels(channel_id=self.channel_id).set(0)  # type: ignore
            except Exception:
                pass
            if thumb_task:
                thumb_task.cancel()
            if monitor_task:
                monitor_task.cancel()
            if db_task:
                db_task.cancel()


def load_channel_config(path: str) -> Dict:
    p = Path(path)
    with p.open("r") as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mobasher Archive Recorder")
    parser.add_argument("--config", required=True, help="Path to channel YAML config")
    parser.add_argument("--data-root", default=os.environ.get("MOBASHER_DATA_ROOT", "../data"))
    parser.add_argument("--mode", choices=["copy", "encode"], default="copy")
    parser.add_argument("--quality", default="720p")
    # Boolean flags for thumbnails
    parser.add_argument("--thumbs", dest="thumbs", action="store_true", default=True)
    parser.add_argument("--no-thumbs", dest="thumbs", action="store_false")
    parser.add_argument("--thumb-format", choices=["jpg", "png"], default="jpg")
    parser.add_argument("--thumb-height", type=int, default=720)
    parser.add_argument("--thumb-offset", type=int, default=3)
    parser.add_argument("--duration-minutes", type=int, default=10, help="Archive segment duration in minutes")
    parser.add_argument("--metrics-port", type=int, default=9120)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    cfg = load_channel_config(args.config)
    data_root = Path(args.data_root)
    data_root.mkdir(parents=True, exist_ok=True)

    opts = ArchiveOptions(
        mode=args.mode,
        quality=args.quality,
        thumbs=bool(args.thumbs),
        thumb_format=args.thumb_format,
        thumb_height=int(args.thumb_height),
        thumb_offset_sec=int(args.thumb_offset),
        segment_seconds=int(args.duration_minutes) * 60,  # Convert minutes to seconds
    )

    if args.metrics_port and args.metrics_port > 0:
        try:
            start_http_server(args.metrics_port)  # type: ignore
            logger.info("Archive metrics on :%s", args.metrics_port)
        except Exception as e:
            logger.warning("metrics start failed: %s", e)

    rec = ArchiveRecorder(cfg, data_root, opts)
    asyncio.run(rec.run())


if __name__ == "__main__":
    main()


