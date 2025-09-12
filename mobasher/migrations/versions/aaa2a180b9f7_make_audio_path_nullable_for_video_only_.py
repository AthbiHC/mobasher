"""make audio_path nullable for video-only segments

Revision ID: aaa2a180b9f7
Revises: 1cbf7c536f4d
Create Date: 2025-09-12 13:20:21.377234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aaa2a180b9f7'
down_revision: Union[str, Sequence[str], None] = '1cbf7c536f4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make audio_path nullable to support video-only segments
    op.alter_column('segments', 'audio_path', nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert audio_path to NOT NULL (this might fail if there are NULL values)
    op.alter_column('segments', 'audio_path', nullable=False)
