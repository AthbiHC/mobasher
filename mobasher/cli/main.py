from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Mediaview CLI - manage recorder, database, services, tests, and info")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run(cmd: str, cwd: Optional[Path] = None) -> int:
    return subprocess.call(cmd, shell=True, cwd=str(cwd) if cwd else None)


@app.command()
def version() -> None:
    """Show CLI version (derived from git)."""
    _run("git describe --tags --always | cat", cwd=_repo_root())


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
def recorder_stop(force: bool = typer.Option(True, help="Also kill lingering ffmpeg with Mobasher UA")) -> None:
    rc = _run("pkill -f 'ingestion/recorder.py' || true", cwd=_repo_root())
    if force:
        # Terminate any ffmpeg processes started by our recorder (identified by UA)
        _run("pkill -f \"ffmpeg.*Mobasher/1.0\" || true", cwd=_repo_root())
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
    inc = " --include-channels" if include_channels else ""
    code = _run(f"python -m mobasher.storage.truncate_db --yes{inc}")
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
    code = _run(cmd)
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


def main() -> None:
    app()


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


if __name__ == "__main__":
    main()


