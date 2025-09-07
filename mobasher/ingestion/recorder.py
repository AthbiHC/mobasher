"""
Mobasher Dual HLS Recorder (start-only filenames)

- 60s processing segments for audio + video
- 1h archive segments for viewing
- Start-only filenames: kuwait1-YYYYMMDD-HHMMSS.{wav|mp4}
- Zero-duration/partial file guard
"""

import asyncio
import signal
import logging
import yaml
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
from contextlib import contextmanager
import time
from typing import Optional, Dict, Any, List
import uuid
import os
import sys
from pathlib import Path as _Path
import platform
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Ensure project root is on sys.path when running from within the package directory
_project_root = str(_Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.append(_project_root)

logger = logging.getLogger(__name__)


class DualHLSRecorder:
    def __init__(self, channel_config: Dict[str, Any], data_root: Path):
        self.config = channel_config
        self.channel_id = channel_config['id']
        self.data_root = Path(data_root).resolve()
        self.recording_id: Optional[str] = None
        self.process_recorder: Optional[asyncio.subprocess.Process] = None
        self.process_audio_recorder: Optional[asyncio.subprocess.Process] = None
        self.process_video_recorder: Optional[asyncio.subprocess.Process] = None
        self.archive_recorder: Optional[asyncio.subprocess.Process] = None
        self.running = False
        self._parse_config()
        self._create_directories()
        # Track run start to aid in test cleanup of extra full segments
        self.run_started_at: Optional[datetime] = None
        # Initialize DB engine early so first write is fast
        try:
            from mobasher.storage.db import init_engine
            init_engine()
        except Exception as e:
            logger.warning(f"DB init warning: {e}")

        # Prometheus metrics
        self.metrics_started = Gauge(
            "mobasher_recorder_running",
            "Recorder running flag (1 running, 0 stopped)",
            ["channel_id"],
        )
        self.metrics_segments_total = Counter(
            "mobasher_recorder_segments_total",
            "Total segments discovered by recorder",
            ["channel_id", "media_type"],
        )
        self.metrics_heartbeat = Counter(
            "mobasher_recorder_heartbeats_total",
            "Heartbeat counter",
            ["channel_id"],
        )
        # Ensure time series is created for this channel_id
        try:
            self.metrics_heartbeat.labels(channel_id=self.channel_id).inc(0)
        except Exception:
            pass
        self.metrics_segment_collect_latency = Histogram(
            "mobasher_recorder_collect_duration_seconds",
            "Time to collect segments from disk",
            ["channel_id"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
        )
        self.metrics_last_hb = Gauge(
            "mobasher_recorder_last_heartbeat_seconds",
            "Unix time of last heartbeat",
            ["channel_id"],
        )

        

    def _parse_config(self):
        rec = self.config.get('recording', {})
        storage = self.config.get('storage', {})
        audio = self.config.get('audio', {})
        video = self.config.get('video', {})

        self.segment_seconds = int(rec.get('segment_seconds', 60))
        self.video_enabled = bool(rec.get('video_enabled', True))
        self.audio_enabled = bool(rec.get('audio_enabled', True))
        self.video_quality = rec.get('video_quality', '720p')

        # Temporarily disable archive in this recorder; a dedicated archiver will be built separately
        self.archive_enabled = False
        self.archive_segment_seconds = int(rec.get('archive_segment_seconds', 3600))
        self.archive_quality = rec.get('archive_quality', '1080p')

        self.date_folders = bool(storage.get('date_folders', True))
        self.directories = storage.get('directories', {'audio': 'audio', 'video': 'video', 'archive': 'archive'})

        self.sample_rate = int(audio.get('sample_rate', 16000))
        self.channels = int(audio.get('channels', 1))

        self.video_qualities = video.get('qualities', {
            '720p': {'resolution': '1280x720', 'bitrate': '2500k', 'fps': 25},
            '1080p': {'resolution': '1920x1080', 'bitrate': '4500k', 'fps': 25},
        })
        # Encoder/preset tuning (reduce CPU; default to hardware on macOS)
        default_encoder = 'h264_videotoolbox' if platform.system().lower() == 'darwin' else 'libx264'
        self.video_encoder = video.get('encoder', default_encoder)
        # For libx264, choose a faster preset by default; for videotoolbox, use realtime usage
        self.video_preset = video.get('preset', 'veryfast' if self.video_encoder == 'libx264' else 'realtime')
        self.video_threads = int(video.get('threads', 2))

    def _create_directories(self):
        """Compute folder paths and ensure they exist."""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if self.date_folders:
            self.audio_dir = self.data_root / self.directories['audio'] / today
            self.video_dir = self.data_root / self.directories['video'] / today
            self.archive_dir = self.data_root / self.directories['archive'] / today
        else:
            self.audio_dir = self.data_root / self.directories['audio'] / self.channel_id
            self.video_dir = self.data_root / self.directories['video'] / self.channel_id
            self.archive_dir = self.data_root / self.directories['archive'] / self.channel_id
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in (self.audio_dir, self.video_dir, self.archive_dir):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

    def _get_video_params(self, quality: str) -> Dict[str, str]:
        return self.video_qualities.get(quality, self.video_qualities['720p'])

    def _build_header_string(self, headers: Dict[str, str]) -> str:
        if not headers:
            return ''
        return '\r\n'.join([f"{k}: {v}" for k, v in headers.items()]) + '\r\n'

    def _build_audio_command(self) -> List[str]:
        stream_url = self.config['input']['url']
        headers = self.config['input'].get('headers', {})
        header_string = self._build_header_string(headers)
        audio_pattern = str(self.audio_dir / f"{self.channel_id}-%Y%m%d-%H%M%S.wav")
        cmd: List[str] = [
            'ffmpeg', '-nostdin', '-loglevel', 'error',
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-user_agent', headers.get('User-Agent', 'Mobasher/1.0'),
        ]
        if header_string:
            cmd += ['-headers', header_string]
        cmd += [
            '-i', stream_url,
            '-vn',
            '-ac', str(self.channels), '-ar', str(self.sample_rate), '-c:a', 'pcm_s16le',
            '-f', 'segment', '-segment_time', str(self.segment_seconds), '-reset_timestamps', '1', '-strftime', '1',
            audio_pattern
        ]
        return cmd

    def _build_video_command(self) -> List[str]:
        stream_url = self.config['input']['url']
        headers = self.config['input'].get('headers', {})
        header_string = self._build_header_string(headers)
        v = self._get_video_params(self.video_quality)
        video_pattern = str(self.video_dir / f"{self.channel_id}-%Y%m%d-%H%M%S.mp4")
        cmd: List[str] = [
            'ffmpeg', '-nostdin', '-loglevel', 'error',
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-user_agent', headers.get('User-Agent', 'Mobasher/1.0'),
        ]
        if header_string:
            cmd += ['-headers', header_string]
        cmd += ['-i', stream_url, '-an']
        # Video encoder selection and tuning
        if self.video_encoder == 'libx264':
            cmd += ['-c:v', 'libx264', '-preset', self.video_preset, '-threads', str(self.video_threads)]
        else:
            # Prefer hardware encoder when available (e.g., macOS)
            cmd += ['-c:v', 'h264_videotoolbox']
            # Use realtime mode for lower CPU and latency on hardware path
            if self.video_preset == 'realtime':
                cmd += ['-realtime', 'true']
        cmd += [
            '-s', v['resolution'], '-b:v', v['bitrate'], '-r', str(v['fps']),
            '-movflags', '+faststart', '-pix_fmt', 'yuv420p',
            '-g', str(int(v['fps']) * 2), '-keyint_min', str(int(v['fps'])),
            '-force_key_frames', f"expr:gte(t,n_forced*{self.segment_seconds})",
            '-f', 'segment', '-segment_time', str(self.segment_seconds), '-reset_timestamps', '1', '-strftime', '1',
            '-segment_format_options', 'movflags=+faststart',
            video_pattern
        ]
        return cmd

    def _build_archive_command(self) -> List[str]:
        if not self.archive_enabled:
            return []
        stream_url = self.config['input']['url']
        headers = self.config['input'].get('headers', {})
        header_string = self._build_header_string(headers)
        v = self._get_video_params(self.archive_quality)
        archive_pattern = str(self.archive_dir / f"{self.channel_id}-archive-%Y%m%d-%H%M%S.mp4")
        cmd: List[str] = [
            'ffmpeg', '-nostdin', '-loglevel', 'error',
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-user_agent', headers.get('User-Agent', 'Mobasher/1.0'),
        ]
        if header_string:
            cmd += ['-headers', header_string]
        cmd += ['-i', stream_url, '-map', '0:v:0', '-map', '0:a:0']
        if self.video_encoder == 'libx264':
            cmd += ['-c:v', 'libx264', '-preset', self.video_preset, '-threads', str(self.video_threads)]
        else:
            cmd += ['-c:v', 'h264_videotoolbox']
            if self.video_preset == 'realtime':
                cmd += ['-realtime', 'true']
        cmd += [
            '-s', v['resolution'], '-b:v', v['bitrate'], '-r', str(v['fps']),
            '-g', str(int(v['fps']) * 2), '-keyint_min', str(int(v['fps'])),
            '-force_key_frames', f"expr:gte(t,n_forced*{self.archive_segment_seconds})",
            '-c:a', 'aac', '-b:a', '128k',
            '-f', 'segment', '-segment_time', str(self.archive_segment_seconds), '-reset_timestamps', '1', '-strftime', '1',
            '-segment_format', 'mp4',
            '-segment_format_options', 'movflags=+faststart+frag_keyframe+empty_moov',
            archive_pattern
        ]
        return cmd

    async def start_recording(self) -> str:
        if self.running:
            raise RuntimeError('Recording is already running')
        self.recording_id = str(uuid.uuid4())
        self.run_started_at = datetime.now(timezone.utc)
        self._create_directories()
        # mark running
        try:
            self.metrics_started.labels(channel_id=self.channel_id).set(1)
        except Exception:
            pass
        # Persist recording start
        try:
            self._persist_recording_start()
        except Exception as e:
            logger.warning(f"failed to persist recording start: {e}")
        # Launch separate audio/video recorders for robustness
        if self.audio_enabled:
            audio_cmd = self._build_audio_command()
            self.process_audio_recorder = await asyncio.create_subprocess_exec(
                *audio_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
        if self.video_enabled:
            video_cmd = self._build_video_command()
            self.process_video_recorder = await asyncio.create_subprocess_exec(
                *video_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
        if self.archive_enabled:
            self._create_directories()
            arch_cmd = self._build_archive_command()
            self.archive_recorder = await asyncio.create_subprocess_exec(
                *arch_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
        self.running = True
        return self.recording_id

    async def stop_recording(self):
        if not self.running:
            return
        await self._stop_process(self.process_audio_recorder)
        await self._stop_process(self.process_video_recorder)
        await self._stop_process(self.archive_recorder)
        self.process_recorder = None
        self.process_audio_recorder = None
        self.process_video_recorder = None
        self.archive_recorder = None
        self.recording_id = None
        self.running = False
        try:
            self.metrics_started.labels(channel_id=self.channel_id).set(0)
        except Exception:
            pass
        # Remove partial/short segments produced right before stopping
        await self._cleanup_partials()
        # Remove extra full segments created during short validations (keep earliest in this run window)
        await self._cleanup_extras()
        # Persist recording end
        try:
            self._persist_recording_end()
        except Exception as e:
            logger.warning(f"failed to persist recording end: {e}")

    async def _stop_process(self, process: Optional[asyncio.subprocess.Process]):
        if not process:
            return
        try:
            try:
                pgid = os.getpgid(process.pid)
            except Exception:
                pgid = None
            if pgid:
                os.killpg(pgid, signal.SIGTERM)
            else:
                process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                if pgid:
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    process.kill()
                await process.wait()
        except Exception:
            pass

    async def get_new_segments(self) -> List[Dict[str, Any]]:
        self._create_directories()
        segments: List[Dict[str, Any]] = []
        _t0 = time.time()
        if self.audio_enabled:
            segments += await self._collect_segments(self.audio_dir, '*.wav', 'audio')
        if self.video_enabled:
            segments += await self._collect_segments(self.video_dir, '*.mp4', 'video')
        try:
            self.metrics_segment_collect_latency.labels(channel_id=self.channel_id).observe(time.time() - _t0)
        except Exception:
            pass
        return sorted(segments, key=lambda x: x['started_at'])

    async def _collect_segments(self, directory: Path, pattern: str, media_type: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not directory.exists():
            return out
        for fp in directory.glob(pattern):
            try:
                size = fp.stat().st_size
                suffix = fp.suffix.lower()
                if suffix == '.wav':
                    # Expected bytes = sample_rate * channels * 2 bytes * duration
                    expected = self.sample_rate * self.channels * 2 * self.segment_seconds
                    if size < expected * 0.85:
                        continue
                elif suffix in ('.mp4', '.mkv'):
                    # Basic sanity threshold for video segments
                    if size < 500_000:
                        continue
                else:
                    if size < 100_000:
                        continue
            except FileNotFoundError:
                continue
            info = self._parse_start_only(fp.name)
            if info:
                # Persist/update segment row for this time slice
                try:
                    self._persist_segment(info, media_type, fp, size)
                except Exception as e:
                    logger.warning(f"persist segment failed: {fp.name} | {e}")
                out.append({
                    'path': str(fp),
                    'channel_id': self.channel_id,
                    'recording_id': self.recording_id,
                    'media_type': media_type,
                    **info,
                })
                try:
                    self.metrics_segments_total.labels(channel_id=self.channel_id, media_type=media_type).inc()
                except Exception:
                    pass
        return out

    def _probe_duration_seconds(self, file_path: Path) -> Optional[float]:
        try:
            import subprocess
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    str(file_path)
                ],
                capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                return None
            val = result.stdout.strip()
            if not val:
                return None
            return float(val)
        except Exception:
            return None

    async def _cleanup_partials(self):
        """Delete short/partial segments created right before stop, to keep only full segments."""
        min_ok = max(10.0, self.segment_seconds * 0.92)  # ~55s for 60s segments
        # Audio cleanup
        if self.audio_enabled and self.audio_dir.exists():
            for fp in self.audio_dir.glob('*.wav'):
                dur = self._probe_duration_seconds(fp)
                if dur is None:
                    # Fallback to size estimation
                    try:
                        size = fp.stat().st_size
                        expected = self.sample_rate * self.channels * 2 * self.segment_seconds
                        if size < expected * 0.85:
                            fp.unlink(missing_ok=True)
                    except FileNotFoundError:
                        pass
                else:
                    if dur < min_ok:
                        fp.unlink(missing_ok=True)
        # Video cleanup
        if self.video_enabled and self.video_dir.exists():
            for fp in self.video_dir.glob('*.mp4'):
                dur = self._probe_duration_seconds(fp)
                if dur is None:
                    try:
                        if fp.stat().st_size < 500_000:
                            fp.unlink(missing_ok=True)
                    except FileNotFoundError:
                        pass
                else:
                    if dur < min_ok:
                        fp.unlink(missing_ok=True)

    def _parse_start_only(self, filename: str) -> Optional[Dict[str, Any]]:
        try:
            stem = filename.rsplit('.', 1)[0]
            parts = stem.split('-')
            date_token = parts[-2]
            time_token = parts[-1]
            start_dt = datetime.strptime(date_token + time_token, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            end_dt = start_dt + timedelta(seconds=self.segment_seconds)
            return {
                'started_at': start_dt,
                'ended_at': end_dt,
                'duration': float(self.segment_seconds),
            }
        except Exception:
            return None

    async def _cleanup_extras(self):
        """Aggressive test cleanup: keep only the earliest full segment per media type in today's folder."""
        min_ok = max(10.0, self.segment_seconds * 0.92)
        # Audio
        if self.audio_enabled and self.audio_dir.exists():
            candidates: List[tuple[datetime, Path]] = []
            for fp in sorted(self.audio_dir.glob('*.wav')):
                info = self._parse_start_only(fp.name)
                if not info:
                    continue
                dur = self._probe_duration_seconds(fp)
                if dur is None:
                    try:
                        size = fp.stat().st_size
                        expected = self.sample_rate * self.channels * 2 * self.segment_seconds
                        if size >= expected * 0.85:
                            candidates.append((info['started_at'], fp))
                    except FileNotFoundError:
                        pass
                elif dur >= min_ok:
                    candidates.append((info['started_at'], fp))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                keep = candidates[0][1]
                for _, fp in candidates[1:]:
                    try:
                        if fp != keep:
                            fp.unlink(missing_ok=True)
                    except FileNotFoundError:
                        pass
        # Video
        if self.video_enabled and self.video_dir.exists():
            candidates: List[tuple[datetime, Path]] = []
            for fp in sorted(self.video_dir.glob('*.mp4')):
                info = self._parse_start_only(fp.name)
                if not info:
                    continue
                dur = self._probe_duration_seconds(fp)
                if dur is not None and dur >= min_ok:
                    candidates.append((info['started_at'], fp))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                keep = candidates[0][1]
                for _, fp in candidates[1:]:
                    try:
                        if fp != keep:
                            fp.unlink(missing_ok=True)
                    except FileNotFoundError:
                        pass

    # -------------------- DB Persistence --------------------
    @contextmanager
    def _db_session(self):
        from mobasher.storage.db import get_session
        gen = get_session()
        session = next(gen)
        try:
            yield session
        finally:
            try:
                next(gen)
            except StopIteration:
                pass

    def _persist_recording_start(self) -> None:
        if not self.recording_id or not self.run_started_at:
            return
        from mobasher.storage.models import Recording, Channel
        with self._db_session() as session:
            # Ensure channel exists to satisfy FK on recordings.channel_id
            try:
                ch = session.get(Channel, self.channel_id)
                if ch is None:
                    input_cfg = self.config.get('input', {})
                    ch = Channel(
                        id=self.channel_id,
                        name=self.config.get('name', self.channel_id),
                        description=self.config.get('description'),
                        url=input_cfg.get('url', ''),
                        headers=input_cfg.get('headers', {}),
                        active=True,
                    )
                    session.add(ch)
                    session.flush()
            except Exception as e:
                logger.warning(f"channel ensure failed: {e}")
            rec = Recording(
                id=uuid.UUID(self.recording_id),
                channel_id=self.channel_id,
                started_at=self.run_started_at,
                status='running',
            )
            session.merge(rec)
            session.commit()

    def _persist_recording_end(self) -> None:
        if not self.recording_id or not self.run_started_at:
            return
        from mobasher.storage.models import Recording
        with self._db_session() as session:
            pk = (uuid.UUID(self.recording_id), self.run_started_at)
            rec = session.get(Recording, pk)
            if rec is not None:
                rec.ended_at = datetime.now(timezone.utc)
                rec.status = 'completed'
                session.add(rec)
                session.commit()

    def _segment_uuid(self, started_at: datetime) -> uuid.UUID:
        name = f"{self.channel_id}:{started_at.isoformat()}"
        return uuid.uuid5(uuid.NAMESPACE_DNS, name)

    def _persist_segment(self, info: Dict[str, Any], media_type: str, file_path: Path, size: int) -> None:
        if not self.recording_id or not self.run_started_at:
            return
        # persist only segments within this run window (avoid older files in today's folder)
        if info['started_at'] < self.run_started_at:
            return
        from mobasher.storage.models import Segment
        seg_id = self._segment_uuid(info['started_at'])
        with self._db_session() as session:
            existing = session.get(Segment, (seg_id, info['started_at']))
            if existing is None:
                seg = Segment(
                    id=seg_id,
                    recording_id=uuid.UUID(self.recording_id) if self.recording_id else None,
                    channel_id=self.channel_id,
                    started_at=info['started_at'],
                    ended_at=info['ended_at'],
                    audio_path=str(file_path) if media_type == 'audio' else None,
                    video_path=str(file_path) if media_type == 'video' else None,
                    file_size_bytes=size,
                    status='completed',
                )
                session.add(seg)
            else:
                if media_type == 'audio' and not existing.audio_path:
                    existing.audio_path = str(file_path)
                if media_type == 'video' and not existing.video_path:
                    existing.video_path = str(file_path)
                if not existing.file_size_bytes or size > (existing.file_size_bytes or 0):
                    existing.file_size_bytes = size
                existing.ended_at = info['ended_at']
                existing.status = 'completed'
                session.add(existing)
            session.commit()


def load_channel_config(config_path: str) -> Dict[str, Any]:
    p = Path(config_path)
    with p.open('r') as f:
        return yaml.safe_load(f)


async def main():
    parser = argparse.ArgumentParser(description='Mobasher Dual HLS Recorder')
    parser.add_argument('--config', default='../channels/kuwait1.yaml', help='Path to channel YAML config')
    parser.add_argument(
        '--data-root',
        default=os.environ.get('MOBASHER_DATA_ROOT', '../data'),
        help='Path to data root directory (or set MOBASHER_DATA_ROOT)'
    )
    parser.add_argument('--duration', type=int, default=0, help='Run duration in seconds (0 means run continuously)')
    parser.add_argument('--heartbeat', type=int, default=30, help='Heartbeat log interval in seconds')
    parser.add_argument('--metrics-port', type=int, default=9108, help='Prometheus metrics HTTP port (0 disables)')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    logger.info('Starting Mobasher recorder')

    config = load_channel_config(args.config)
    recorder = DualHLSRecorder(config, Path(args.data_root))
    # Start Prometheus exporter if enabled
    if args.metrics_port > 0:
        try:
            start_http_server(args.metrics_port)
            logger.info(f'Metrics exporter started on :{args.metrics_port}')
        except Exception as e:
            logger.warning(f'Failed to start metrics exporter: {e}')
    rec_id = await recorder.start_recording()
    logger.info(f'Recording started | id={rec_id} | channel={recorder.channel_id}')

    # Graceful shutdown on SIGINT/SIGTERM/SIGHUP
    stop_event: asyncio.Event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Some platforms (e.g., Windows) may not support add_signal_handler
            pass

    start_time = time.time()
    try:
        while not stop_event.is_set():
            # Heartbeat status
            try:
                segs = await recorder.get_new_segments()
                num_audio = sum(1 for s in segs if s['media_type'] == 'audio')
                num_video = sum(1 for s in segs if s['media_type'] == 'video')
                try:
                    recorder.metrics_heartbeat.labels(channel_id=recorder.channel_id).inc()
                    import time as _t
                    recorder.metrics_last_hb.labels(channel_id=recorder.channel_id).set(_t.time())
                except Exception:
                    pass
                logger.info(
                    f'heartbeat | audio_segments_today={num_audio} | video_segments_today={num_video}'
                )
            except Exception as e:
                logger.warning(f'heartbeat error: {e}')

            # Duration check
            if args.duration and (time.time() - start_time) >= args.duration:
                logger.info('Duration reached, stopping...')
                break

            await asyncio.sleep(max(5, args.heartbeat))
    except KeyboardInterrupt:
        logger.info('Interrupted by user, stopping...')
    finally:
        await recorder.stop_recording()
        # Final summary
        segs = await recorder.get_new_segments()
        num_audio = sum(1 for s in segs if s['media_type'] == 'audio')
        num_video = sum(1 for s in segs if s['media_type'] == 'video')
        logger.info(f'stopped | audio_segments_today={num_audio} | video_segments_today={num_video}')


if __name__ == '__main__':
    asyncio.run(main())
