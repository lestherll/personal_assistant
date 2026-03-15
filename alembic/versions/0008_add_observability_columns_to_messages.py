"""Add observability columns to messages

Adds sequence_index (monotonic per-conversation ordering), provider, model,
prompt_tokens, and completion_tokens for cost analysis and turn ordering.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("sequence_index", sa.Integer, nullable=True))
    op.add_column("messages", sa.Column("provider", sa.String(255), nullable=True))
    op.add_column("messages", sa.Column("model", sa.String(255), nullable=True))
    op.add_column("messages", sa.Column("prompt_tokens", sa.Integer, nullable=True))
    op.add_column("messages", sa.Column("completion_tokens", sa.Integer, nullable=True))

    op.create_unique_constraint(
        "uq_messages_conversation_sequence",
        "messages",
        ["conversation_id", "sequence_index"],
    )
    op.create_index(
        "idx_messages_conversation_sequence",
        "messages",
        ["conversation_id", "sequence_index"],
    )


def downgrade() -> None:
    op.drop_index("idx_messages_conversation_sequence", table_name="messages")
    op.drop_constraint("uq_messages_conversation_sequence", "messages", type_="unique")
    op.drop_column("messages", "completion_tokens")
    op.drop_column("messages", "prompt_tokens")
    op.drop_column("messages", "model")
    op.drop_column("messages", "provider")
    op.drop_column("messages", "sequence_index")
