"""Rename messages.metadata to messages.extra_metadata

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("messages", "metadata", new_column_name="extra_metadata")


def downgrade() -> None:
    op.alter_column("messages", "extra_metadata", new_column_name="metadata")
