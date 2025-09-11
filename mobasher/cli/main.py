from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
import json
import time
from datetime import datetime, timezone, timedelta

app = typer.Typer(help="Mediaview CLI - manage recorder, database, services, tests, and info")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run(cmd: str, cwd: Optional[Path] = None) -> int:
    return subprocess.call(cmd, shell=True, cwd=str(cwd) if cwd else None)


@app.command()
def version() -> None:
    """Show CLI version (derived from git)."""
    _run("git describe --tags --always | cat", cwd=_repo_root())
# -------------------- Central short commands --------------------


@app.command("status")
def status(json_out: bool = typer.Option(False, "--json", help="Emit JSON output")) -> None:
    """Show system health summary: DB, Redis, API, recent segments/transcripts."""
    result: Dict[str, Any] = {
        "db": {"status": "unknown"},
        "redis": {"status": "unknown"},
        "api": {"status": "unknown"},
        "pipeline": {"segments_10m": 0, "transcripts_10m": 0},
    }
    exit_code = 0

    # DB checks and recent counts
    try:
        from mobasher.storage.db import get_session, init_engine
        from mobasher.storage.models import Segment, Transcript
        init_engine()
        with next(get_session()) as db:  # type: ignore
            now = datetime.now(timezone.utc)
            since = now - timedelta(minutes=10)
            segs_10m = db.query(Segment).filter(Segment.started_at >= since).count()
            trs_10m = (
                db.query(Transcript)
                .filter(Transcript.segment_started_at >= since)
                .count()
            )
            result["pipeline"]["segments_10m"] = int(segs_10m)
            result["pipeline"]["transcripts_10m"] = int(trs_10m)
            result["db"]["status"] = "ok"
    except Exception as e:
        result["db"] = {"status": "error", "detail": str(e)}
        exit_code = 1

    # Redis
    try:
        import os as _os
        import redis as _redis  # type: ignore
        r = _redis.from_url(_os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        pong = r.ping()
        result["redis"]["status"] = "ok" if pong else "error"
        if not pong:
            exit_code = 1
    except Exception as e:
        result["redis"] = {"status": "error", "detail": str(e)}
        exit_code = 1

    # API
    try:
        import os as _os
        import httpx  # type: ignore
        host = _os.environ.get("API_HOST", "127.0.0.1")
        port = int(_os.environ.get("API_PORT", "8010"))
        url = f"http://{host}:{port}/health"
        resp = httpx.get(url, timeout=2.0)
        ok = (resp.status_code == 200 and resp.json().get("status") == "ok")
        result["api"]["status"] = "ok" if ok else "error"
        if not ok:
            exit_code = 1
    except Exception as e:
        result["api"] = {"status": "error", "detail": str(e)}
        exit_code = 1

    # Overall status
    all_ok = (
        result["db"]["status"] == "ok"
        and result["redis"]["status"] == "ok"
        and result["api"]["status"] == "ok"
    )
    result["status"] = "green" if all_ok else "red"

    if json_out:
        typer.echo(json.dumps(result, default=str))
    else:
        typer.echo(
            "\n".join(
                [
                    f"DB: {result['db']['status']}",
                    f"Redis: {result['redis']['status']}",
                    f"API: {result['api']['status']}",
                    f"Segments (10m): {result['pipeline']['segments_10m']} | Transcripts (10m): {result['pipeline']['transcripts_10m']}",
                    f"Overall: {result['status']}",
                ]
            )
        )
    raise typer.Exit(exit_code)


channels_app = typer.Typer(help="Channels management")
app.add_typer(channels_app, name="channels")


@channels_app.command("list")
def channels_list(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output"),
    active_only: bool = typer.Option(False, help="Show only active channels"),
    limit: int = typer.Option(100, help="Max results"),
    offset: int = typer.Option(0, help="Offset for pagination"),
) -> None:
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.repositories import list_channels as _list_channels
    init_engine()
    with next(get_session()) as db:  # type: ignore
        items = _list_channels(db, active_only=active_only, limit=limit, offset=offset)
        if json_out:
            out = [
                {
                    "id": ch.id,
                    "name": ch.name,
                    "active": ch.active,
                    "url": ch.url,
                }
                for ch in items
            ]
            typer.echo(json.dumps(out, default=str))
        else:
            for ch in items:
                typer.echo(f"{ch.id}\t{ch.name}\t{'active' if ch.active else 'inactive'}")


@channels_app.command("add")
def channels_add(
    channel_id: str = typer.Argument(..., help="Channel id (unique)"),
    name: str = typer.Option(..., help="Channel display name"),
    url: str = typer.Option(..., help="Stream URL"),
    active: bool = typer.Option(True, help="Active flag"),
    description: Optional[str] = typer.Option(None, help="Optional description"),
) -> None:
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.repositories import upsert_channel
    init_engine()
    with next(get_session()) as db:  # type: ignore
        ch = upsert_channel(db, channel_id=channel_id, name=name, url=url, headers={}, active=active, description=description)
        typer.echo(f"upserted channel: {ch.id} ({'active' if ch.active else 'inactive'})")


@channels_app.command("enable")
def channels_enable(channel_id: str = typer.Argument(...)) -> None:
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.repositories import get_channel, upsert_channel
    init_engine()
    with next(get_session()) as db:  # type: ignore
        ch = get_channel(db, channel_id)
        if ch is None:
            raise typer.Exit(2)
        upsert_channel(
            db,
            channel_id=channel_id,
            name=ch.name,
            url=ch.url,
            headers=ch.headers,
            active=True,
            description=ch.description,
        )
        typer.echo(f"enabled channel: {channel_id}")


@channels_app.command("disable")
def channels_disable(channel_id: str = typer.Argument(...)) -> None:
    from mobasher.storage.db import get_session, init_engine
    from mobasher.storage.repositories import get_channel, upsert_channel
    init_engine()
    with next(get_session()) as db:  # type: ignore
        ch = get_channel(db, channel_id)
        if ch is None:
            raise typer.Exit(2)
        upsert_channel(
            db,
            channel_id=channel_id,
            name=ch.name,
            url=ch.url,
            headers=ch.headers,
            active=False,
            description=ch.description,
        )
        typer.echo(f"disabled channel: {channel_id}")


# -------------------- Screenshots helpers --------------------

screenshots_app = typer.Typer(help="Screenshots operations")
app.add_typer(screenshots_app, name="screenshots")


@screenshots_app.command("latest")
def screenshots_latest(
    channel_id: Optional[str] = typer.Option(None),
    limit: int = typer.Option(12),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    import httpx  # type: ignore
    import os as _os
    host = _os.environ.get("API_HOST", "127.0.0.1")
    port = int(_os.environ.get("API_PORT", "8010"))
    params = {"limit": str(limit)}
    if channel_id:
        params["channel_id"] = channel_id
    url = f"http://{host}:{port}/screenshots"
    r = httpx.get(url, params=params, timeout=5.0)
    r.raise_for_status()
    data = r.json()
    if json_out:
        typer.echo(json.dumps(data))
    else:
        for it in data.get("items", []):
            typer.echo(f"{it['created_at']}\t{it['channel_id']}\t{it['screenshot_path']}")


@vision_app.command("enqueue-screenshots")
def vision_enqueue_screenshots(limit: int = typer.Option(12)) -> None:
    import sys
    code = _run(
        f"{sys.executable} -c 'from mobasher.vision.enqueue import enqueue_screenshots_for_recent; print(enqueue_screenshots_for_recent({limit}))' | cat",
        cwd=_repo_root(),
    )
    raise typer.Exit(code)


recorder_app = typer.Typer(help="Recorder management")
app.add_typer(recorder_app, name="recorder")


@recorder_app.command("start")
def recorder_start(
    config: str = typer.Option(..., help="Path to channel YAML (e.g., mobasher/channels/kuwait1.yaml)"),
    data_root: Optional[str] = typer.Option(None, help="Data root (overrides MOBASHER_DATA_ROOT)"),
    heartbeat: int = typer.Option(15, help="Heartbeat seconds"),
    daemon: bool = typer.Option(True, help="Run in background using nohup"),
    metrics_port: Optional[int] = typer.Option(None, help="Prometheus metrics port (recorder)"),
) -> None:
    env = os.environ.copy()
    import sys
    # Resolve config relative to repo root so it works from ingestion/ cwd
    cfg_path = config
    if not os.path.isabs(cfg_path):
        cfg_candidate = _repo_root() / cfg_path
        cfg_path = str(cfg_candidate.resolve())
    if data_root:
        env["MOBASHER_DATA_ROOT"] = data_root
    metrics_flag = f" --metrics-port {metrics_port}" if metrics_port else ""
    base_cmd = f"{sys.executable} recorder.py --config {cfg_path} --heartbeat {heartbeat}{metrics_flag}"
    cmd = f"nohup {base_cmd} > recorder.log 2>&1 &" if daemon else base_cmd
    typer.echo(f"Executing: {cmd}")
    code = subprocess.call(cmd, shell=True, cwd=str(_repo_root() / "mobasher/ingestion"), env=env)
    raise typer.Exit(code)


@recorder_app.command("status")
def recorder_status() -> None:
    code = _run("pgrep -af 'ingestion/recorder.py' || echo 'Recorder not running'", cwd=_repo_root())
    raise typer.Exit(code)


@recorder_app.command("stop")
def recorder_stop(force: bool = typer.Option(True, help="Also kill lingering ffmpeg and metrics ports")) -> None:
    root = _repo_root()
    rc = _run("pkill -f 'ingestion/recorder.py' || true", cwd=root)
    if force:
        # Kill ffmpeg processes launched by our recorder (User-Agent marker)
        _run("pkill -f \"ffmpeg.*Mobasher/1.0\" || true", cwd=root)
        # Close common recorder metrics ports (multi-channel ready)
        for port in (9108, 9109, 9110, 9111, 9112):
            _run(f"PID=$(lsof -tiTCP:{port} -sTCP:LISTEN || true); [ -n \"$PID\" ] && kill -KILL $PID || true", cwd=root)
    raise typer.Exit(rc)


@recorder_app.command("logs")
def recorder_logs(follow: bool = typer.Option(False, "-f", "--follow")) -> None:
    cmd = "tail -f recorder.log" if follow else "tail -n 200 recorder.log"
    code = _run(cmd, cwd=_repo_root() / "mobasher/ingestion")
    raise typer.Exit(code)


db_app = typer.Typer(help="Database operations")
app.add_typer(db_app, name="db")


@db_app.command("truncate")
def db_truncate(include_channels: bool = typer.Option(False), yes: bool = typer.Option(False)) -> None:
    if not yes:
        typer.echo("Refusing to run without --yes")
        raise typer.Exit(2)
    import sys
    inc = " --include-channels" if include_channels else ""
    code = _run(f"{sys.executable} -m mobasher.storage.truncate_db --yes{inc}")
    raise typer.Exit(code)


@db_app.command("retention")
def db_retention(
    transcripts_days: int = typer.Option(365, "--transcripts-days"),
    embeddings_days: int = typer.Option(365, "--embeddings-days"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    if not dry_run and not yes:
        typer.echo("Refusing to run without --yes (or use --dry-run)")
        raise typer.Exit(2)
    flags = " --dry-run" if dry_run else " --yes"
    cmd = (
        "python -m mobasher.storage.retention_jobs"
        f"{flags} --retain-transcripts-days {transcripts_days} --retain-embeddings-days {embeddings_days}"
    )
    code = _run(cmd, cwd=_repo_root())
    raise typer.Exit(code)


services_app = typer.Typer(help="Docker services")
app.add_typer(services_app, name="services")


@services_app.command("up")
def services_up() -> None:
    code = _run("docker-compose up -d postgres redis", cwd=_repo_root() / "mobasher/docker")
    raise typer.Exit(code)


@services_app.command("down")
def services_down() -> None:
    code = _run("docker-compose down", cwd=_repo_root() / "mobasher/docker")
    raise typer.Exit(code)


@services_app.command("ps")
def services_ps() -> None:
    code = _run("docker-compose ps", cwd=_repo_root() / "mobasher/docker")
    raise typer.Exit(code)


tests_app = typer.Typer(help="Test helpers")
app.add_typer(tests_app, name="tests")


@tests_app.command("integration")
def tests_integration() -> None:
    cmd = "PYTHONPATH=. mobasher/venv/bin/python -m pytest -q mobasher/tests/test_db_integration.py | cat"
    code = _run(cmd, cwd=_repo_root())
    raise typer.Exit(code)


info_app = typer.Typer(help="Info and diagnostics")
app.add_typer(info_app, name="info")


@info_app.command("env")
def info_env() -> None:
    db_user = os.environ.get("DB_USER", "mobasher")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "mobasher")
    data_root = os.environ.get("MOBASHER_DATA_ROOT", "<default ../data>")
    typer.echo(f"DB: postgresql://{db_user}:<redacted>@{db_host}:{db_port}/{db_name}")
    typer.echo(f"DATA_ROOT: {data_root}")


@info_app.command("config")
def info_config() -> None:
    typer.echo("Config file support will be added in v1.1 (mediaview.yaml)")


api_app = typer.Typer(help="API server")
app.add_typer(api_app, name="api")


@api_app.command("serve")
def api_serve(
    host: str = typer.Option("127.0.0.1", help="Bind host (defaults to localhost)"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, help="Auto-reload on code changes"),
    public: bool = typer.Option(False, help="Bind to 0.0.0.0 (overrides host)"),
) -> None:
    import sys
    # Use the same interpreter (venv) to ensure uvicorn runs within it
    bind_host = "0.0.0.0" if public else host
    cmd = f"{sys.executable} -m uvicorn mobasher.api.app:app --host {bind_host} --port {port}"
    if reload:
        cmd += " --reload"
    code = _run(cmd, cwd=_repo_root())
    raise typer.Exit(code)


asr_app = typer.Typer(help="ASR pipeline")
app.add_typer(asr_app, name="asr")


@asr_app.command("worker")
def asr_worker(metrics_port: int = typer.Option(9109, help="Prometheus metrics port for ASR worker"),
               pool: str = typer.Option("solo", help="Celery pool (solo,prefork,threads)"),
               concurrency: int = typer.Option(1, help="Worker concurrency")) -> None:
    import sys
    # Use the same interpreter to run celery to avoid PATH issues
    env_prefix = f"ASR_METRICS_PORT={metrics_port} " if metrics_port else ""
    cmd = f"{env_prefix}{sys.executable} -m celery -A mobasher.asr.worker.app worker --loglevel=INFO -P {pool} -c {concurrency}"
    code = _run(cmd, cwd=_repo_root())
    raise typer.Exit(code)


@asr_app.command("ping")
def asr_ping() -> None:
    code = _run("python -c 'from mobasher.asr.worker import ping; print(ping.delay().get(timeout=5))' | cat", cwd=_repo_root())
    raise typer.Exit(code)


@asr_app.command("enqueue")
def asr_enqueue(
    channel_id: Optional[str] = typer.Option(None, help="Filter by channel id"),
    since: Optional[str] = typer.Option(None, help="ISO timestamp to start from (UTC)"),
    limit: int = typer.Option(200, help="Max segments to enqueue"),
) -> None:
    import sys
    code = _run(
        f"{sys.executable} -c 'from mobasher.asr.enqueue import enqueue_missing; import datetime as _d; print(enqueue_missing({repr(channel_id)}, _d.datetime.fromisoformat(\"{since}\") if {repr(bool(since))} else None, {limit}))' | cat",
        cwd=_repo_root(),
    )
    raise typer.Exit(code)


@asr_app.command("scheduler")
def asr_scheduler(
    channel_id: Optional[str] = typer.Option(None, help="Filter by channel id"),
    interval: int = typer.Option(30, help="Polling interval seconds"),
    lookback: int = typer.Option(10, help="Lookback minutes"),
) -> None:
    code = _run(f"python -c 'from mobasher.asr.scheduler import run_scheduler_blocking; run_scheduler_blocking(channel_id={repr(channel_id)}, interval_seconds={interval}, lookback_minutes={lookback})'", cwd=_repo_root())
    raise typer.Exit(code)


@asr_app.command("bench")
def asr_bench(
    path: str = typer.Option(..., help="First audio file path"),
    path2: Optional[str] = typer.Option(None, help="Second audio file path"),
    path3: Optional[str] = typer.Option(None, help="Third audio file path"),
    models: str = typer.Option("small,medium", help="Comma-separated models"),
    beam: int = typer.Option(5),
    vad: bool = typer.Option(False),
    word_ts: bool = typer.Option(False),
    device: Optional[str] = typer.Option(None),
) -> None:
    paths = [path] + ([path2] if path2 else []) + ([path3] if path3 else [])
    arg_paths = " ".join([f"--path '{p}'" for p in paths])
    vad_flag = "--vad" if vad else "--no-vad"
    wts_flag = "--word-ts" if word_ts else "--no-word-ts"
    cmd = f"python -m mobasher.asr.bench run {arg_paths} --models '{models}' --beam {beam} {vad_flag} {wts_flag}" + (f" --device {device}" if device else "")
    code = _run(cmd, cwd=_repo_root())
    raise typer.Exit(code)


vision_app = typer.Typer(help="Vision pipeline")
app.add_typer(vision_app, name="vision")


@vision_app.command("worker")
def vision_worker(concurrency: int = typer.Option(2, help="Celery worker concurrency")) -> None:
    import sys
    cmd = f"{sys.executable} -m celery -A mobasher.vision.worker.app worker --loglevel=INFO -c {concurrency}"
    code = _run(cmd, cwd=_repo_root())
    raise typer.Exit(code)


@vision_app.command("enqueue")
def vision_enqueue(limit: int = typer.Option(20, help="How many segments to enqueue")) -> None:
    import sys
    code = _run(
        f"{sys.executable} -c 'from mobasher.vision.enqueue import enqueue_vision_for_asr_processed; print(enqueue_vision_for_asr_processed({limit}))' | cat",
        cwd=_repo_root(),
    )
    raise typer.Exit(code)


# Archive recorder commands
archive_app = typer.Typer(help="Archive recorder (hour-aligned)")
app.add_typer(archive_app, name="archive")


@archive_app.command("start")
def archive_start(
    config: str = typer.Option(..., help="Path to channel YAML"),
    data_root: Optional[str] = typer.Option(None, help="Data root (overrides MOBASHER_DATA_ROOT)"),
    mode: str = typer.Option("copy", help="copy|encode"),
    quality: str = typer.Option("720p"),
    thumbs: bool = typer.Option(True, help="Create thumbnails per archive file"),
    metrics_port: int = typer.Option(9120, help="Metrics port"),
    daemon: bool = typer.Option(True, help="Run in background via nohup"),
) -> None:
    import sys
    env = os.environ.copy()
    cfg_path = config
    if not os.path.isabs(cfg_path):
        cfg_path = str((_repo_root() / cfg_path).resolve())
    if data_root:
        env["MOBASHER_DATA_ROOT"] = data_root
    thumb_flag = "--thumbs" if thumbs else "--no-thumbs"
    data_flag = f" --data-root {data_root}" if data_root else ""
    base = (
        f"{sys.executable} archive_recorder.py --config {cfg_path}{data_flag} "
        f"--mode {mode} --quality {quality} {thumb_flag} --metrics-port {metrics_port}"
    )
    cmd = f"nohup {base} > archive_{Path(cfg_path).stem}.log 2>&1 &" if daemon else base
    typer.echo(f"Executing: {cmd}")
    code = _run(cmd, cwd=_repo_root() / "mobasher/ingestion")
    raise typer.Exit(code)


@archive_app.command("status")
def archive_status() -> None:
    code = _run("pgrep -af 'ingestion/archive_recorder.py' || echo 'Archive not running'", cwd=_repo_root())
    raise typer.Exit(code)


@archive_app.command("stop")
def archive_stop() -> None:
    root = _repo_root()
    _run("pkill -f 'ingestion/archive_recorder.py' || true", cwd=root)
    # close default metrics port if stuck
    for port in (9120, 9121, 9122):
        _run(f"PID=$(lsof -tiTCP:{port} -sTCP:LISTEN || true); [ -n \"$PID\" ] && kill -KILL $PID || true", cwd=root)
    raise typer.Exit(0)

# Fresh reset (renamed to single word) and kill commands


def _kill_processes() -> None:
    """Stop recorder/ffmpeg and workers; close known metrics ports."""
    root = _repo_root()
    _run("pkill -f 'ingestion/recorder.py' || true", cwd=root)
    _run("pkill -f \"ffmpeg.*Mobasher/1.0\" || true", cwd=root)
    _run("pkill -f \"ffmpeg.*Media-View/mobasher/data/\" || true", cwd=root)
    _run("pkill -f 'celery.*mobasher.asr.worker' || true", cwd=root)
    _run("pkill -f 'celery.*mobasher.vision.worker' || true", cwd=root)
    for port in (9108, 9109, 9110):
        _run(f"PID=$(lsof -tiTCP:{port} -sTCP:LISTEN || true); [ -n \"$PID\" ] && kill -KILL $PID || true", cwd=root)


def _wipe_data_roots(extra_root: Optional[str], today_only: bool) -> None:
    import shutil
    import re as _re
    from datetime import datetime, timezone

    roots: List[Path] = []
    root = _repo_root()
    roots.append(root / "mobasher" / "data")
    roots.append(root / "data")
    env_root = os.environ.get("MOBASHER_DATA_ROOT")
    if extra_root:
        env_root = extra_root
    if env_root:
        roots.append(Path(env_root))

    def _safe(root_path: Path) -> bool:
        try:
            return root_path.exists() and root_path.is_dir() and root_path.name.lower() == "data"
        except Exception:
            return False

    channel_like = _re.compile(r"^(al_|sky|cnbc|kuwait|mbc|aj|[a-z0-9_\-]+)$", _re.IGNORECASE)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for dr in roots:
        if not _safe(dr):
            continue
        for p in dr.iterdir():
            try:
                if p.is_dir():
                    if today_only:
                        # Only remove today's dated subfolders under any channel or media dir
                        if _re.match(r"^\d{4}-\d{2}-\d{2}$", p.name) and p.name == today:
                            shutil.rmtree(p, ignore_errors=True)
                    else:
                        if channel_like.match(p.name) or p.name in {"audio", "video", "screenshots", "gallery"} or _re.match(r"^\d{4}-\d{2}-\d{2}$", p.name):
                            shutil.rmtree(p, ignore_errors=True)
                else:
                    if not today_only and p.suffix.lower() in {".wav", ".mp4", ".mkv", ".jpg", ".jpeg", ".json", ".jsonl"}:
                        try:
                            p.unlink()
                        except Exception:
                            pass
            except FileNotFoundError:
                pass


@app.command("freshreset")
def fresh_reset(
    include_channels: bool = typer.Option(False, help="Also truncate channels table"),
    yes: bool = typer.Option(False, help="Confirm reset (required)"),
    data_root: Optional[str] = typer.Option(None, help="Override MOBASHER_DATA_ROOT for wiping"),
    today_only: bool = typer.Option(False, help="Only wipe today's folders (YYYY-MM-DD)"),
) -> None:
    """Stop processes, truncate DB, and wipe data directories."""
    if not yes:
        typer.echo("Refusing to run without --yes")
        raise typer.Exit(2)
    typer.echo("Stopping recorder/workers and closing metrics ports…")
    _kill_processes()
    typer.echo("Truncating database tables…")
    import sys
    inc = " --include-channels" if include_channels else ""
    rc = _run(f"{sys.executable} -m mobasher.storage.truncate_db --yes{inc}")
    if rc != 0:
        raise typer.Exit(rc)
    typer.echo("Wiping data directories…")
    _wipe_data_roots(data_root, today_only)
    typer.echo("Fresh reset completed.")


@app.command("kill-the-minions")
def kill_the_minions() -> None:
    """Kill all Mobasher-related processes (recorder, ffmpeg, ASR, vision, metrics)."""
    _kill_processes()
    typer.echo("All minions are terminated.")


# Backward-compatible alias
@app.command("kill-minions")
def kill_minions_alias() -> None:
    _kill_processes()
    typer.echo("All minions are terminated.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()


