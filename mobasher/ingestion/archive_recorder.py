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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

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
    segment_seconds: int = 3600  # fixed at 1 hour


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

        try:
            self.metrics_running.labels(channel_id=self.channel_id).set(0)
        except Exception:
            pass

    def _ffmpeg_base(self) -> list[str]:
        stream_url = self.cfg["input"]["url"]
        headers = self.cfg["input"].get("headers", {})
        header_string = _build_header_string(headers)
        cmd: list[str] = [
            "ffmpeg", "-nostdin", "-loglevel", "error",
            "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
            "-user_agent", headers.get("User-Agent", "Mobasher/1.0"),
        ]
        if header_string:
            cmd += ["-headers", header_string]
        cmd += ["-i", stream_url]
        return cmd

    def _ffmpeg_output_pattern(self) -> str:
        # data/archive/<channel_id>/%Y-%m-%d/<channel_id>-%Y-%m-%d-%H-00-00.mp4
        return str(self.archive_dir_base / "%Y-%m-%d" / f"{self.channel_id}-%Y-%m-%d-%H-00-00.mp4")

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

        # hour-aligned segmenting
        cmd += [
            "-f", "segment",
            "-segment_atclocktime", "1",
            "-segment_clocktime", str(self.opts.segment_seconds),
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
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )
        return proc

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
        vf = f"scale=-2:{self.opts.thumb_height}:flags=lanczos"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(self.opts.thumb_offset_sec),
            "-i", str(mp4_path),
            "-frames:v", "1",
            "-vf", vf,
        ]
        if self.opts.thumb_format.lower() == "jpg":
            cmd += ["-q:v", "2"]
        cmd += [str(out_path)]
        await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)

    async def run(self) -> None:
        try:
            self.metrics_running.labels(channel_id=self.channel_id).set(1)  # type: ignore
        except Exception:
            pass
        thumb_task: Optional[asyncio.Task] = None
        if self.opts.thumbs:
            thumb_task = asyncio.create_task(self._thumbnail_worker())
        proc = await self._spawn_ffmpeg()
        try:
            await proc.wait()
        finally:
            try:
                self.metrics_running.labels(channel_id=self.channel_id).set(0)  # type: ignore
            except Exception:
                pass
            if thumb_task:
                thumb_task.cancel()


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


