from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Cross-dialect JSON type: uses JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
_JSON = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


class MessageRole(enum.StrEnum):
    """Valid values for Message.role. Enforced as a PostgreSQL enum type."""

    human = "human"
    ai = "ai"
    system = "system"
    tool = "tool"


class Base(DeclarativeBase):
    pass


class User(Base):
    """Application user account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    workspaces: Mapped[list[UserWorkspace]] = relationship(
        "UserWorkspace", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!s}, username={self.username!r})"


class UserWorkspace(Base):
    """A user-scoped workspace (forked from the default template)."""

    __tablename__ = "user_workspaces"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_workspace_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship("User", back_populates="workspaces")
    agents: Mapped[list[UserAgent]] = relationship(
        "UserAgent", back_populates="workspace", cascade="all, delete-orphan"
    )
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="workspace", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"UserWorkspace(id={self.id!s}, name={self.name!r})"


class UserAgent(Base):
    """An agent configuration belonging to a user workspace."""

    __tablename__ = "user_agents"
    __table_args__ = (UniqueConstraint("user_workspace_id", "name", name="uq_user_agent_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    allowed_tools: Mapped[list[str] | None] = mapped_column(_JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    workspace: Mapped[UserWorkspace] = relationship("UserWorkspace", back_populates="agents")

    def __repr__(self) -> str:
        return f"UserAgent(id={self.id!s}, name={self.name!r})"


class UserAPIKey(Base):
    """An API key belonging to a user for programmatic access."""

    __tablename__ = "user_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return f"UserAPIKey(id={self.id!s}, name={self.name!r}, prefix={self.key_prefix!r})"


class Conversation(Base):
    """Represents a single conversation session within a user's workspace."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    workspace: Mapped[UserWorkspace] = relationship("UserWorkspace", back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.sequence_index",
        cascade="all, delete-orphan",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=True, default="Untitled Conversation")

    def __repr__(self) -> str:
        return f"Conversation(id={self.id!s}, workspace_id={self.workspace_id!s})"


# Cross-dialect enum: uses a native PostgreSQL ENUM on Postgres, plain VARCHAR elsewhere.
_MessageRoleType = PgEnum(
    MessageRole,
    name="message_role",
    create_type=False,  # created by migration 0005
).with_variant(String(50), "sqlite")


class Message(Base):
    """A single message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(_MessageRoleType, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional structured metadata (tool call details, etc.)
    extra_metadata: Mapped[dict[str, object] | None] = mapped_column(_JSON, nullable=True)
    # Which agent produced this message (nullable for human messages and if agent deleted)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Monotonic ordering within a conversation (assigned by repository with row lock)
    sequence_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Observability: which provider/model produced this message and token counts
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        preview = self.content[:40].replace("\n", " ")
        return f"Message(role={self.role!r}, content={preview!r})"
