"""Add conversation title

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-17 18:43:21.471887
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("title", sa.String(length=255), nullable=True))

    # backfill existing conversations with empty title
    # to first message content or "Untitled Conversation"
    op.execute("""
        UPDATE conversations
        SET title = COALESCE(
            (SELECT substring(content FROM 1 FOR 255)
               FROM messages
               WHERE messages.conversation_id = conversations.id
               ORDER BY created_at
               LIMIT 1),
            'Untitled Conversation'
        )
        WHERE title IS NULL OR title = '';
    """)


def downgrade() -> None:
    op.drop_column("conversations", "title")
