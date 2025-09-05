"""timescale_policies: retention and compression for hypertables

Revision ID: 66501cbbea91
Revises: f761abb86757
Create Date: 2025-09-05 19:56:39.839217

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66501cbbea91'
down_revision: Union[str, Sequence[str], None] = 'f761abb86757'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable compression on hypertables and add retention/compression policies (idempotent)
    op.execute("ALTER TABLE IF EXISTS recordings SET (timescaledb.compress, timescaledb.compress_segmentby = 'channel_id')")
    op.execute("ALTER TABLE IF EXISTS segments SET (timescaledb.compress, timescaledb.compress_segmentby = 'channel_id')")
    op.execute("ALTER TABLE IF EXISTS visual_events SET (timescaledb.compress, timescaledb.compress_segmentby = 'channel_id')")
    op.execute("ALTER TABLE IF EXISTS system_metrics SET (timescaledb.compress, timescaledb.compress_segmentby = 'metric_name')")

    # Add compression policies if missing
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression' AND hypertable_name = 'recordings'
            ) THEN
                PERFORM add_compression_policy('recordings', INTERVAL '7 days');
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression' AND hypertable_name = 'segments'
            ) THEN
                PERFORM add_compression_policy('segments', INTERVAL '7 days');
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression' AND hypertable_name = 'visual_events'
            ) THEN
                PERFORM add_compression_policy('visual_events', INTERVAL '1 day');
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression' AND hypertable_name = 'system_metrics'
            ) THEN
                PERFORM add_compression_policy('system_metrics', INTERVAL '1 day');
            END IF;
        END$$;
        """
    )

    # Add retention policies if missing
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' AND hypertable_name = 'recordings'
            ) THEN
                PERFORM add_retention_policy('recordings', INTERVAL '365 days');
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' AND hypertable_name = 'segments'
            ) THEN
                PERFORM add_retention_policy('segments', INTERVAL '365 days');
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' AND hypertable_name = 'visual_events'
            ) THEN
                PERFORM add_retention_policy('visual_events', INTERVAL '90 days');
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention' AND hypertable_name = 'system_metrics'
            ) THEN
                PERFORM add_retention_policy('system_metrics', INTERVAL '90 days');
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove policies if they exist; leave compression setting as-is
    def remove_if_exists(proc: str, hypertable: str, remove_sql: str) -> None:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = '{proc}' AND hypertable_name = '{hypertable}'
                ) THEN
                    PERFORM {remove_sql};
                END IF;
            END$$;
            """
        )

    remove_if_exists('policy_compression', 'recordings', "remove_compression_policy('recordings')")
    remove_if_exists('policy_retention', 'recordings', "remove_retention_policy('recordings')")
    remove_if_exists('policy_compression', 'segments', "remove_compression_policy('segments')")
    remove_if_exists('policy_retention', 'segments', "remove_retention_policy('segments')")
    remove_if_exists('policy_compression', 'visual_events', "remove_compression_policy('visual_events')")
    remove_if_exists('policy_retention', 'visual_events', "remove_retention_policy('visual_events')")
    remove_if_exists('policy_compression', 'system_metrics', "remove_compression_policy('system_metrics')")
    remove_if_exists('policy_retention', 'system_metrics', "remove_retention_policy('system_metrics')")
