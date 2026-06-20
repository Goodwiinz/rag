"""Unit tests: DO KB hot-path retrieve timeout → hybrid-fallback trigger.

Regression guard for the asyncio.wait_for wrap added in _nodes_rag.py.
Verifies that:
  - a slow retrieve (simulated via asyncio.sleep) returns None within the
    configured timeout so _legacy_hybrid_search_fallback fires, rather than
    hanging for the full HTTP retry window (~90 s).
  - a fast successful retrieve surfaces its chunks normally (happy path
    unaffected).

Patch strategy
--------------
_try_primary_do_kb_read uses lazy ``from X import Y`` bindings inside the
function body.  The right patch targets are therefore the *source* modules,
not aliases in _nodes_rag:

  - ``src.core.config.settings``      → controls DO_KB_PRIMARY_READ /
                                         DO_KB_RETRIEVE_TIMEOUT_SECONDS
  - ``src.core.database.AsyncSessionLocal`` (lazy import)
  - ``src.models.organization.Organization`` (lazy import — not used directly,
    only passed to session.get; we mock the session)
  - ``src.services.do_kb.get_do_kb_client`` (lazy import)
  - ``src.services.do_kb.resolve.resolve_and_filter_chunks`` (lazy import)
  - ``src.services.agent._nodes_rag._shape_do_kb_context``
    (module-level helper; patch at the _nodes_rag namespace)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent._nodes_rag import _try_primary_do_kb_read

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_user(org_id: str = "org-abc") -> MagicMock:
    user = MagicMock()
    user.organization_id = org_id
    return user


def _make_chunk(text: str = "chunk text") -> MagicMock:
    chunk = MagicMock()
    chunk.text = text
    return chunk


def _make_retrieve_result(chunks: list) -> MagicMock:
    result = MagicMock()
    result.chunks = chunks
    return result


def _make_mock_session(kb_uuid: Optional[str] = "kb-uuid-123"):
    """Return an async context-manager mock whose session.get yields an org."""
    org = MagicMock()
    org.do_kb_uuid = kb_uuid

    session = AsyncMock()
    session.get = AsyncMock(return_value=org)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


def _mock_settings(primary_read: bool = True, timeout: float = 0.2) -> MagicMock:
    cfg = MagicMock()
    cfg.DO_KB_PRIMARY_READ = primary_read
    cfg.DO_KB_RETRIEVE_TIMEOUT_SECONDS = timeout
    return cfg


# ---------------------------------------------------------------------------
# Test 1: slow retrieve → returns None within tight timeout
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_slow_do_kb_retrieve_returns_none_quickly():
    """A retrieve that sleeps 10 s must not block; function returns None fast.

    We set DO_KB_RETRIEVE_TIMEOUT_SECONDS=0.2 so the test finishes in well
    under a second rather than the production 3 s.
    """

    async def _slow_retrieve(**_kwargs):
        await asyncio.sleep(10)  # far longer than the 0.2 s cap
        return _make_retrieve_result([_make_chunk()])

    slow_client = MagicMock()
    slow_client.retrieve = _slow_retrieve

    with (
        patch("src.core.config.settings", new=_mock_settings(timeout=0.2)),
        patch(
            "src.core.database.AsyncSessionLocal",
            new=_make_mock_session(),
        ),
        patch(
            "src.services.do_kb.get_do_kb_client",
            return_value=slow_client,
        ),
    ):
        result = await _try_primary_do_kb_read(
            query="what is the capital of France?",
            current_user=_make_user(),
        )

    # Must return None (triggering fallback) — not the slow chunk list
    assert result is None


# ---------------------------------------------------------------------------
# Test 2: fast retrieve → returns chunks (happy path unaffected)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fast_do_kb_retrieve_returns_contexts():
    """A fast retrieve surfaces shaped contexts, not None."""
    chunk = _make_chunk("Paris is the capital of France.")
    fast_result = _make_retrieve_result([chunk])

    fast_client = MagicMock()
    fast_client.retrieve = AsyncMock(return_value=fast_result)

    fake_context = {
        "document_id": "doc-1",
        "title": "Geography",
        "content": "Paris is the capital of France.",
        "score": 0.95,
    }

    with (
        patch("src.core.config.settings", new=_mock_settings(timeout=3.0)),
        patch(
            "src.core.database.AsyncSessionLocal",
            new=_make_mock_session(),
        ),
        patch(
            "src.services.do_kb.get_do_kb_client",
            return_value=fast_client,
        ),
        patch(
            "src.services.do_kb.resolve.resolve_and_filter_chunks",
            new=AsyncMock(return_value=({"doc-1": "Geography"}, [chunk])),
        ),
        patch(
            "src.services.agent._nodes_rag._shape_do_kb_context",
            return_value=fake_context,
        ),
    ):
        result = await _try_primary_do_kb_read(
            query="what is the capital of France?",
            current_user=_make_user(),
        )

    assert result is not None
    assert len(result) == 1
    assert result[0]["content"] == "Paris is the capital of France."
