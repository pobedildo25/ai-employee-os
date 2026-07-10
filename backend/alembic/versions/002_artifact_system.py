"""artifact system with versioning

Revision ID: 002
Revises: 001
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

artifact_status = postgresql.ENUM(
    "DRAFT",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "ARCHIVED",
    name="artifact_status",
    create_type=False,
)


def upgrade() -> None:
    artifact_status.create(op.get_bind(), checkfirst=True)

    op.add_column("artifacts", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "artifacts",
        sa.Column(
            "status",
            artifact_status,
            nullable=False,
            server_default="DRAFT",
        ),
    )
    op.add_column("artifacts", sa.Column("mime_type", sa.String(length=255), nullable=True))
    op.add_column("artifacts", sa.Column("size", sa.BigInteger(), nullable=True))
    op.add_column("artifacts", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("artifacts", sa.Column("created_by", sa.String(length=255), nullable=True))

    op.alter_column("artifacts", "storage_path", existing_type=sa.String(length=1024), nullable=True)
    op.drop_column("artifacts", "version")

    op.create_table(
        "artifact_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id", "version_number", name="uq_artifact_version_number"),
    )
    op.create_index(op.f("ix_artifact_versions_artifact_id"), "artifact_versions", ["artifact_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_artifact_versions_artifact_id"), table_name="artifact_versions")
    op.drop_table("artifact_versions")

    op.add_column("artifacts", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.alter_column("artifacts", "storage_path", existing_type=sa.String(length=1024), nullable=False)

    op.drop_column("artifacts", "created_by")
    op.drop_column("artifacts", "metadata")
    op.drop_column("artifacts", "size")
    op.drop_column("artifacts", "mime_type")
    op.drop_column("artifacts", "status")
    op.drop_column("artifacts", "description")

    artifact_status.drop(op.get_bind(), checkfirst=True)
