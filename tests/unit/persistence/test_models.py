"""Unit tests for persistence/models.py (no DB connection required)."""

from __future__ import annotations

import uuid
from datetime import UTC

from personal_assistant.persistence.models import Conversation, Message, _now


class TestConversationModel:
    def test_repr_contains_workspace_id(self):
        ws_id = uuid.uuid4()
        conv = Conversation(workspace_id=ws_id)
        r = repr(conv)
        assert str(ws_id) in r

    def test_id_column_has_uuid4_default(self):

        mapper = Conversation.__mapper__
        id_col = mapper.columns["id"]
        assert id_col.default is not None

    def test_created_at_is_timezone_aware(self):
        dt = _now()
        assert dt.tzinfo is not None
        assert dt.tzinfo == UTC


class TestMessageModel:
    def test_repr_contains_role(self):
        conv_id = uuid.uuid4()
        msg = Message(conversation_id=conv_id, role="human", content="Hello there")
        r = repr(msg)
        assert "human" in r

    def test_repr_truncates_content_at_40_chars(self):
        conv_id = uuid.uuid4()
        msg = Message(conversation_id=conv_id, role="ai", content="A" * 60)
        r = repr(msg)
        # The repr shows at most 40 chars of content preview
        assert "A" * 41 not in r
        assert "A" * 40 in r

    def test_repr_replaces_newlines(self):
        conv_id = uuid.uuid4()
        msg = Message(conversation_id=conv_id, role="human", content="line1\nline2")
        r = repr(msg)
        assert "\n" not in r
