"""Add message_role enum type and migrate messages.role

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-15 00:00:00.000000

Pre-flight check before running:
    SELECT DISTINCT role FROM messages;
Normalise any unexpected role values before applying this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE public.message_role AS ENUM ('human', 'ai', 'system', 'tool')")
    op.alter_column(
        "messages",
        "role",
        type_=sa.Enum("human", "ai", "system", "tool", name="message_role"),
        existing_type=sa.String(50),
        postgresql_using="role::public.message_role",
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "messages",
        "role",
        type_=sa.String(50),
        existing_type=sa.Enum("human", "ai", "system", "tool", name="message_role"),
        postgresql_using="role::varchar",
        nullable=False,
    )
    op.execute("DROP TYPE public.message_role")
