"""knowledge items table

Revision ID: 004
Revises: 003
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_items_client_id"), "knowledge_items", ["client_id"], unique=False)
    op.create_index(op.f("ix_knowledge_items_category"), "knowledge_items", ["category"], unique=False)
    op.create_index(
        op.f("ix_knowledge_items_source_artifact_id"),
        "knowledge_items",
        ["source_artifact_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_items_source_artifact_id"), table_name="knowledge_items")
    op.drop_index(op.f("ix_knowledge_items_category"), table_name="knowledge_items")
    op.drop_index(op.f("ix_knowledge_items_client_id"), table_name="knowledge_items")
    op.drop_table("knowledge_items")
