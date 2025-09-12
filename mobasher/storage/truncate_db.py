"""
Utility script to truncate Mobasher database tables for a fresh start.

Usage:
  source venv/bin/activate
  python -m mobasher.storage.truncate_db --yes

By default, requires --yes to proceed. Set --force to skip prompt (CI).
"""
from __future__ import annotations

import argparse
from typing import Sequence

from sqlalchemy import text

from .db import init_engine

# Order matters if not using CASCADE. We'll use TRUNCATE ... CASCADE to simplify.
TABLES: Sequence[str] = (
    # Order doesn't matter when using TRUNCATE ... CASCADE
    "visual_events",
    "screenshots",
    "segment_embeddings",
    "transcripts",
    "segments",
    "recordings",
    "entities",
    "alerts",
    "system_metrics",
    # keep channels unless --include-channels specified
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Truncate Mobasher DB tables")
    parser.add_argument("--yes", action="store_true", help="Confirm truncate (required)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    parser.add_argument(
        "--include-channels",
        action="store_true",
        help="Also truncate channels table",
    )
    args = parser.parse_args()

    if not (args.yes or args.force):
        parser.error("Refusing to run without --yes (or --force)")

    engine = init_engine()

    # Determine which target tables actually exist in the current schema
    with engine.begin() as conn:
        existing = {
            r[0]
            for r in conn.execute(
                text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = current_schema()")
            ).fetchall()
        }

        truncate_list = [t for t in TABLES if t in existing]
        if args.include_channels and "channels" in existing:
            truncate_list.append("channels")

        if not truncate_list:
            print("No target tables found to truncate in current schema.")
            return

        # Use TRUNCATE with CASCADE; avoid session_replication_role (often disallowed on managed DBs)
        # PostgreSQL TRUNCATE does not support IF EXISTS for multiple tables in one statement.
        # Execute a single TRUNCATE without IF EXISTS since we filtered to existing tables.
        stmt = "TRUNCATE TABLE " + ", ".join(truncate_list) + " RESTART IDENTITY CASCADE"
        conn.execute(text(stmt))

    print("Truncated:", ", ".join(truncate_list))


if __name__ == "__main__":
    main()
