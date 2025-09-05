"""pgvector: ensure extension and ivfflat index for segment_embeddings.vector

Revision ID: f761abb86757
Revises: b6aa81e4e7b3
Create Date: 2025-09-05 19:55:12.227222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f761abb86757'
down_revision: Union[str, Sequence[str], None] = 'b6aa81e4e7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Create IVFFlat index for faster similarity search (requires rows present to vacuum/analyze before use)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() AND indexname = 'idx_segment_embeddings_vector'
            ) THEN
                CREATE INDEX idx_segment_embeddings_vector ON segment_embeddings USING ivfflat (vector vector_l2_ops) WITH (lists = 100);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_segment_embeddings_vector")
