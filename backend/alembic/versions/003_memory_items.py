"""memory items table

Revision ID: 003
Revises: 002
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_items_type"), "memory_items", ["type"], unique=False)
    op.create_index(op.f("ix_memory_items_client_id"), "memory_items", ["client_id"], unique=False)
    op.create_index(op.f("ix_memory_items_project_id"), "memory_items", ["project_id"], unique=False)
    op.create_index(op.f("ix_memory_items_session_id"), "memory_items", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_items_session_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_project_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_client_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_type"), table_name="memory_items")
    op.drop_table("memory_items")
