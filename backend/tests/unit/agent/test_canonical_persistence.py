"""Unit tests for PR 1 of the server-canonical persistence rollout.

Covers the pieces that don't need a live Postgres:
- the AGENT_CANONICAL_PERSISTENCE flag parsing,
- the deterministic assistant client_message_id derivation contract,
- _persist_assistant_message_safe forwarding the new kwargs
  (latency_ms / stopped / client_message_id) and returning the id.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.api.agent.streaming import _canonical_persistence_enabled


@pytest.mark.unit
class TestCanonicalPersistenceFlag:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("AGENT_CANONICAL_PERSISTENCE", raising=False)
        assert _canonical_persistence_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
    def test_truthy_values(self, monkeypatch, value):
        monkeypatch.setenv("AGENT_CANONICAL_PERSISTENCE", value)
        assert _canonical_persistence_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "off", ""])
    def test_falsy_values(self, monkeypatch, value):
        monkeypatch.setenv("AGENT_CANONICAL_PERSISTENCE", value)
        assert _canonical_persistence_enabled() is False


@pytest.mark.unit
class TestAssistantClientMessageId:
    def test_derivation_is_deterministic(self):
        # Contract used by streaming.py: same user client_message_id must
        # always map to the same assistant key, so an SSE retry of the same
        # turn hits the assistant-role unique index instead of duplicating.
        user_cmid = "3f2b8a44-9c1d-4e5f-8a6b-7c8d9e0f1a2b"
        a = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nous-assistant:{user_cmid}"))
        b = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nous-assistant:{user_cmid}"))
        assert a == b
        assert a != user_cmid

    def test_different_turns_get_different_keys(self):
        a = str(uuid.uuid5(uuid.NAMESPACE_URL, "nous-assistant:turn-1"))
        b = str(uuid.uuid5(uuid.NAMESPACE_URL, "nous-assistant:turn-2"))
        assert a != b


@pytest.mark.unit
class TestPersistSafeForwarding:
    @pytest.mark.asyncio
    async def test_forwards_new_kwargs_and_returns_id(self):
        from src.api.agent import jobs

        captured = {}

        async def _fake_persist(db, **kwargs):
            captured.update(kwargs)
            return "msg-123"

        with (
            patch.object(jobs, "_persist_assistant_message", side_effect=_fake_persist),
            patch.object(jobs, "AsyncSessionLocal") as session_factory,
        ):
            session_factory.return_value.__aenter__ = AsyncMock(return_value=object())
            session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await jobs._persist_assistant_message_safe(
                thread_id="t-1",
                content="partial answer",
                model_name="gpt-5-mini",
                tool_executions_out=None,
                retrieved_contexts=None,
                latency_ms=4200,
                stopped=True,
                client_message_id="cmid-1",
            )

        assert result == "msg-123"
        assert captured["latency_ms"] == 4200
        assert captured["stopped"] is True
        assert captured["client_message_id"] == "cmid-1"

    @pytest.mark.asyncio
    async def test_swallows_errors_and_returns_none(self):
        from src.api.agent import jobs

        with (
            patch.object(
                jobs,
                "_persist_assistant_message",
                side_effect=RuntimeError("db down"),
            ),
            patch.object(jobs, "AsyncSessionLocal") as session_factory,
        ):
            session_factory.return_value.__aenter__ = AsyncMock(return_value=object())
            session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await jobs._persist_assistant_message_safe(
                thread_id="t-1",
                content="x",
                model_name=None,
                tool_executions_out=None,
            )

        assert result is None
