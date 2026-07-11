"""workspace foundation tables

Revision ID: 005
Revises: 004
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["active_artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["active_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["active_task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index(op.f("ix_workspaces_active_project_id"), "workspaces", ["active_project_id"], unique=False)
    op.create_index(op.f("ix_workspaces_active_session_id"), "workspaces", ["active_session_id"], unique=False)
    op.create_index(op.f("ix_workspaces_active_task_id"), "workspaces", ["active_task_id"], unique=False)
    op.create_index(op.f("ix_workspaces_active_artifact_id"), "workspaces", ["active_artifact_id"], unique=False)

    op.create_table(
        "workspace_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspace_sessions_workspace_id"), "workspace_sessions", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_workspace_sessions_status"), "workspace_sessions", ["status"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["workspace_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )


def downgrade() -> None:
    op.drop_table("conversations")
    op.drop_index(op.f("ix_workspace_sessions_status"), table_name="workspace_sessions")
    op.drop_index(op.f("ix_workspace_sessions_workspace_id"), table_name="workspace_sessions")
    op.drop_table("workspace_sessions")
    op.drop_index(op.f("ix_workspaces_active_artifact_id"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_active_task_id"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_active_session_id"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_active_project_id"), table_name="workspaces")
    op.drop_table("workspaces")
