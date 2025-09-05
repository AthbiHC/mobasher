"""
Retention and cleanup jobs for non-hypertable tables.

TimescaleDB retention policies handle hypertables (e.g., recordings, segments,
visual_events, system_metrics). This script cleans up regular tables that
reference time via segment_started_at: transcripts and segment_embeddings.

Usage:
  source mobasher/venv/bin/activate
  python -m mobasher.storage.retention_jobs --yes \
      --retain-transcripts-days 365 \
      --retain-embeddings-days 365

Notes:
  - Use --dry-run to see what would be deleted.
  - Defaults keep 365 days if not specified.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import text

from .db import init_engine


def delete_older_than(table: str, cutoff_iso: str) -> str:
    if table == "transcripts":
        return (
            "DELETE FROM transcripts \n"
            " WHERE segment_started_at < :cutoff"
        )
    if table == "segment_embeddings":
        return (
            "DELETE FROM segment_embeddings \n"
            " WHERE segment_started_at < :cutoff"
        )
    raise ValueError(f"Unsupported cleanup table: {table}")


def count_older_than(table: str) -> str:
    return f"SELECT count(*) FROM {table} WHERE segment_started_at < :cutoff"


def run_cleanup(retain_transcripts_days: int, retain_embeddings_days: int, dry_run: bool) -> Tuple[int, int]:
    engine = init_engine()
    now = datetime.now(timezone.utc)
    transcripts_cutoff = now - timedelta(days=retain_transcripts_days)
    embeddings_cutoff = now - timedelta(days=retain_embeddings_days)

    deleted_transcripts = 0
    deleted_embeddings = 0

    with engine.begin() as conn:
        # Transcripts
        to_delete_count = conn.execute(
            text(count_older_than("transcripts")), {"cutoff": transcripts_cutoff}
        ).scalar_one()
        if not dry_run and to_delete_count:
            conn.execute(text(delete_older_than("transcripts", transcripts_cutoff.isoformat())), {"cutoff": transcripts_cutoff})
        deleted_transcripts = int(to_delete_count)

        # Embeddings
        to_delete_count = conn.execute(
            text(count_older_than("segment_embeddings")), {"cutoff": embeddings_cutoff}
        ).scalar_one()
        if not dry_run and to_delete_count:
            conn.execute(text(delete_older_than("segment_embeddings", embeddings_cutoff.isoformat())), {"cutoff": embeddings_cutoff})
        deleted_embeddings = int(to_delete_count)

    return deleted_transcripts, deleted_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup transcripts and embeddings by retention periods")
    parser.add_argument("--yes", action="store_true", help="Confirm cleanup (required unless --dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    parser.add_argument("--retain-transcripts-days", type=int, default=365)
    parser.add_argument("--retain-embeddings-days", type=int, default=365)
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        parser.error("Refusing to run without --yes (or use --dry-run)")

    deleted_transcripts, deleted_embeddings = run_cleanup(
        retain_transcripts_days=args.retain_transcripts_days,
        retain_embeddings_days=args.retain_embeddings_days,
        dry_run=args.dry_run,
    )

    mode = "DRY-RUN" if args.dry_run else "DELETED"
    print(f"{mode}: transcripts={deleted_transcripts}, embeddings={deleted_embeddings}")


if __name__ == "__main__":
    main()


