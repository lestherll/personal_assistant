"""Replace conversations.workspace_name string with workspace_id FK

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-15 00:00:00.000000

Pre-flight check before running:
    SELECT COUNT(*) FROM conversations WHERE workspace_id IS NULL;
This must return 0 after the backfill UPDATE below; if not, there are
workspace_name / user_id mismatches that must be resolved manually first.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: add nullable FK column
    op.add_column("conversations", sa.Column("workspace_id", sa.Uuid(as_uuid=True), nullable=True))

    # Step 2: backfill from user_workspaces by name + user_id match
    op.execute(
        """
        UPDATE conversations c
        SET workspace_id = uw.id
        FROM user_workspaces uw
        WHERE uw.name    = c.workspace_name
          AND uw.user_id = c.user_id
        """
    )

    # Step 3: enforce NOT NULL and FK constraint, then drop the old column
    op.alter_column("conversations", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_conversations_workspace_id",
        "conversations",
        "user_workspaces",
        ["workspace_id"],
        ["id"],
    )
    op.drop_column("conversations", "workspace_name")


def downgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("workspace_name", sa.String(255), nullable=True),
    )
    op.execute(
        """
        UPDATE conversations c
        SET workspace_name = uw.name
        FROM user_workspaces uw
        WHERE uw.id = c.workspace_id
        """
    )
    op.alter_column("conversations", "workspace_name", nullable=False)
    op.drop_constraint("fk_conversations_workspace_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "workspace_id")
