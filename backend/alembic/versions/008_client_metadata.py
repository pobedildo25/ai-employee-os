"""clients metadata column

Revision ID: 008
Revises: 007
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        """
        UPDATE clients
        SET metadata = jsonb_build_object('type', 'telegram_user')
        WHERE name LIKE 'Telegram %'
          AND (metadata IS NULL OR metadata = '{}'::jsonb)
        """
    )


def downgrade() -> None:
    op.drop_column("clients", "metadata")
