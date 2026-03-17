"""Add user_api_keys table

Stores hashed API keys for programmatic access. Also makes
user_agents.allowed_tools nullable (NULL = all tools, [] = no tools).

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_api_keys",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # allow_tools: NULL = all tools, [] = no tools
    op.alter_column("user_agents", "allowed_tools", nullable=True)

    # Make allowed_tools nullable (NULL = all tools, [] = no tools)
    # Update existing empty arrays to NULL
    op.execute("UPDATE user_agents SET allowed_tools = NULL WHERE allowed_tools = '[]'")


def downgrade() -> None:
    op.execute("UPDATE user_agents SET allowed_tools = '[]' WHERE allowed_tools IS NULL")
    op.drop_table("user_api_keys")
