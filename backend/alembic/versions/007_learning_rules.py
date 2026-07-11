"""learning_rules table

Revision ID: 007
Revises: 006
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_rules_scope"), "learning_rules", ["scope"], unique=False)
    op.create_index(op.f("ix_learning_rules_category"), "learning_rules", ["category"], unique=False)
    op.create_index(op.f("ix_learning_rules_key"), "learning_rules", ["key"], unique=False)
    op.create_index(op.f("ix_learning_rules_client_id"), "learning_rules", ["client_id"], unique=False)
    op.create_index(op.f("ix_learning_rules_project_id"), "learning_rules", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_rules_project_id"), table_name="learning_rules")
    op.drop_index(op.f("ix_learning_rules_client_id"), table_name="learning_rules")
    op.drop_index(op.f("ix_learning_rules_key"), table_name="learning_rules")
    op.drop_index(op.f("ix_learning_rules_category"), table_name="learning_rules")
    op.drop_index(op.f("ix_learning_rules_scope"), table_name="learning_rules")
    op.drop_table("learning_rules")
