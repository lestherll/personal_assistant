"""Add users and user-scoped resources

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # --- user_workspaces ---
    op.create_table(
        "user_workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_workspace_name"),
    )
    op.create_index("ix_user_workspaces_user_id", "user_workspaces", ["user_id"])

    # --- user_agents ---
    op.create_table(
        "user_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=False, server_default=""),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column(
            "allowed_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_workspace_id"], ["user_workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_workspace_id", "name", name="uq_user_agent_name"),
    )
    op.create_index("ix_user_agents_user_workspace_id", "user_agents", ["user_workspace_id"])

    # --- conversations.user_id FK ---
    op.add_column(
        "conversations",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_user_id",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_constraint("fk_conversations_user_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "user_id")

    op.drop_index("ix_user_agents_user_workspace_id", table_name="user_agents")
    op.drop_table("user_agents")

    op.drop_index("ix_user_workspaces_user_id", table_name="user_workspaces")
    op.drop_table("user_workspaces")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
