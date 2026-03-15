"""Add agent_id FK to messages

Agent participation is tracked at the message level, not the conversation level.
Nullable so that human messages and orphaned rows (agent deleted) remain valid.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("agent_id", sa.Uuid(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_messages_agent_id",
        "messages",
        "user_agents",
        ["agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_agent_id", "messages", type_="foreignkey")
    op.drop_column("messages", "agent_id")
