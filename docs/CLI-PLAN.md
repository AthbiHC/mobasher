# Mediaview CLI Plan

## Overview
A unified command-line tool `mediaview` to manage development and operations of the Media-View system (recorder, database, services, tests, and diagnostics).

## Framework & Packaging
- Framework: Typer (Click-based) for typed, ergonomic CLI with rich `--help`.
- Package: `mobasher/cli/` with a console entrypoint `mediaview`.
- Also runnable via `python -m mobasher.cli`.

## Configuration
- Resolution order: CLI flags > environment variables > config file > defaults.
- Config file (optional): `mediaview.yaml` at repo root.
- Key options: data_root, default channel config path, docker compose path, retention days, DB settings (`DB_*`).

## v1 Commands
- `mediaview --help`: top-level help and examples.

### recorder
- `mediaview recorder start --config ../channels/kuwait1.yaml [--data-root <path>] [--heartbeat <s>] [--daemon]`
- `mediaview recorder status` (pgrep on `ingestion/recorder.py`)
- `mediaview recorder stop` (pkill pattern)
- `mediaview recorder logs [-f|--follow] [--path mobasher/ingestion/recorder.log]`

### db
- `mediaview db migrate [--message <text>] [--autogenerate]`
- `mediaview db upgrade [--rev head]`
- `mediaview db truncate [--yes] [--include-channels]`
- `mediaview db retention [--yes|--dry-run] [--transcripts-days 365] [--embeddings-days 365]`

### services
- `mediaview services up [postgres] [redis]`
- `mediaview services down`
- `mediaview services ps`

### tests
- `mediaview tests integration`

### info
- `mediaview info config` (effective config)
- `mediaview info env` (key envs; redacts passwords)

## v1 Implementation Notes
- Process management: default pgrep/pkill; `--daemon` uses `nohup` for background.
- Destructive ops require `--yes`.
- Alembic invoked via module, ensuring `alembic.ini` path set (or `-c` flag).
- Docker wrappers run in `mobasher/docker`.

## v1.1 Enhancements (Post-v1)
- PID file management for recorder: `mobasher/ingestion/recorder.pid` with `start/stop/status` using the pid.
- JSON output mode (`--json`) for scripting and automation.
- Channel helpers: `channels list/add/enable/disable`.
- `mediaview init` to generate `mediaview.yaml` with sensible defaults.
- Better log management: rotate logs, `--since` filter.

## Rollout Plan
1. Add CLI package and minimal commands with Typer.
2. Wire recorder/db/services/tests/info subcommands.
3. Add console_scripts entry `mediaview`.
4. Update `README.md` and `docs/COMMANDS.md` to include CLI usage.
5. Add simple CI smoke tests (`mediaview --help`, `mediaview info env`).

## Risks & Mitigations
- Cross-platform process control: start with Unix-centric pgrep/pkill; document Windows alternative.
- Alembic environment: ensure we pass the correct `-c <path>` or set `ALEMBIC_CONFIG`.
- Docker presence: guard commands with a clear error if docker is not installed.
