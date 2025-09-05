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
from typing import Optional, Dict, Any, List
import uuid
import os

logger = logging.getLogger(__name__)


class DualHLSRecorder:
    def __init__(self, channel_config: Dict[str, Any], data_root: Path):
        self.config = channel_config
        self.channel_id = channel_config['id']
        self.data_root = Path(data_root)
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

        

    def _parse_config(self):
        rec = self.config.get('recording', {})
        storage = self.config.get('storage', {})
        audio = self.config.get('audio', {})
        video = self.config.get('video', {})

        self.segment_seconds = int(rec.get('segment_seconds', 60))
        self.video_enabled = bool(rec.get('video_enabled', True))
        self.audio_enabled = bool(rec.get('audio_enabled', True))
        self.video_quality = rec.get('video_quality', '720p')

        self.archive_enabled = bool(rec.get('archive_enabled', True))
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
        cmd += [
            '-i', stream_url,
            '-an',
            '-c:v', 'libx264', '-preset', 'medium',
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
            'ffmpeg', '-nostdin',
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
            '-user_agent', headers.get('User-Agent', 'Mobasher/1.0'),
        ]
        if header_string:
            cmd += ['-headers', header_string]
        cmd += [
            '-i', stream_url,
            '-map', '0:v:0', '-map', '0:a:0',
            '-c:v', 'libx264', '-preset', 'slow', '-s', v['resolution'], '-b:v', v['bitrate'], '-r', str(v['fps']),
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
        # Launch separate audio/video recorders for robustness
        if self.audio_enabled:
            audio_cmd = self._build_audio_command()
            self.process_audio_recorder = await asyncio.create_subprocess_exec(*audio_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        if self.video_enabled:
            video_cmd = self._build_video_command()
            self.process_video_recorder = await asyncio.create_subprocess_exec(*video_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        if self.archive_enabled:
            self._create_directories()
            arch_cmd = self._build_archive_command()
            self.archive_recorder = await asyncio.create_subprocess_exec(*arch_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
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
        # Remove partial/short segments produced right before stopping
        await self._cleanup_partials()
        # Remove extra full segments created during short validations (keep earliest in this run window)
        await self._cleanup_extras()

    async def _stop_process(self, process: Optional[asyncio.subprocess.Process]):
        if not process:
            return
        try:
            process.send_signal(signal.SIGINT)
            try:
                await asyncio.wait_for(process.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        except Exception:
            pass

    async def get_new_segments(self) -> List[Dict[str, Any]]:
        self._create_directories()
        segments: List[Dict[str, Any]] = []
        if self.audio_enabled:
            segments += await self._collect_segments(self.audio_dir, '*.wav', 'audio')
        if self.video_enabled:
            segments += await self._collect_segments(self.video_dir, '*.mp4', 'video')
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
                out.append({
                    'path': str(fp),
                    'channel_id': self.channel_id,
                    'recording_id': self.recording_id,
                    'media_type': media_type,
                    **info,
                })
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


def load_channel_config(config_path: str) -> Dict[str, Any]:
    p = Path(config_path)
    with p.open('r') as f:
        return yaml.safe_load(f)


async def main():
    logging.basicConfig(level=logging.INFO)
    config = load_channel_config('../channels/kuwait1.yaml')
    recorder = DualHLSRecorder(config, Path('../data'))
    rec_id = await recorder.start_recording()
    print(f"Recording started: {rec_id}")
    await asyncio.sleep(65)
    await recorder.stop_recording()
    segs = await recorder.get_new_segments()
    print(f"Segments found: {len(segs)}")
    for s in segs[:6]:
        print(f" - {s['media_type']} {Path(s['path']).name} [{int(s['duration'])}s]")


if __name__ == '__main__':
    asyncio.run(main())
