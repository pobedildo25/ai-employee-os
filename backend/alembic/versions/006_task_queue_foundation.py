"""background tasks + workspace active_background_tasks

Revision ID: 006
Revises: 005
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "active_background_tasks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.create_table(
        "background_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_background_tasks_task_type"), "background_tasks", ["task_type"], unique=False)
    op.create_index(op.f("ix_background_tasks_status"), "background_tasks", ["status"], unique=False)
    op.create_index(op.f("ix_background_tasks_priority"), "background_tasks", ["priority"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_background_tasks_priority"), table_name="background_tasks")
    op.drop_index(op.f("ix_background_tasks_status"), table_name="background_tasks")
    op.drop_index(op.f("ix_background_tasks_task_type"), table_name="background_tasks")
    op.drop_table("background_tasks")
    op.drop_column("workspaces", "active_background_tasks")
