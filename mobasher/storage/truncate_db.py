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
    "segment_embeddings",
    "transcripts",
    "visual_events",
    "segments",
    "recordings",
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
    stmts = []
    stmts.append("SET session_replication_role = replica")  # speed up, skip FKs

    truncate_list = list(TABLES)
    if args.include_channels:
        truncate_list.append("channels")

    stmts.append(
        "TRUNCATE TABLE "
        + ", ".join(truncate_list)
        + " RESTART IDENTITY CASCADE"
    )
    stmts.append("SET session_replication_role = DEFAULT")

    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))

    print("Truncated:", ", ".join(truncate_list))


if __name__ == "__main__":
    main()
