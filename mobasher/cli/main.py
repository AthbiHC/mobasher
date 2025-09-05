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
) -> None:
    env = os.environ.copy()
    if data_root:
        env["MOBASHER_DATA_ROOT"] = data_root
    cmd = f"nohup python recorder.py --config {config} --heartbeat {heartbeat} > recorder.log 2>&1 &" if daemon else f"python recorder.py --config {config} --heartbeat {heartbeat}"
    typer.echo(f"Executing: {cmd}")
    code = subprocess.call(cmd, shell=True, cwd=str(_repo_root() / "mobasher/ingestion"), env=env)
    raise typer.Exit(code)


@recorder_app.command("status")
def recorder_status() -> None:
    code = _run("pgrep -af 'ingestion/recorder.py' || echo 'Recorder not running'", cwd=_repo_root())
    raise typer.Exit(code)


@recorder_app.command("stop")
def recorder_stop() -> None:
    code = _run("pkill -f 'ingestion/recorder.py' || true", cwd=_repo_root())
    raise typer.Exit(code)


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()


