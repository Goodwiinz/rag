"""Regression tests for the rag-scope-and-sanitizer audit-remediation item.

Four independent findings covered here:

* M2 -- ``_user_owns_project`` / ``_try_primary_do_kb_read_impl``: a DB
  error during the project-ownership check must abort the DO KB primary
  read (falls back to hybrid search, which re-verifies ownership itself)
  instead of silently widening the read to the whole org.
* M3 -- ``rag_node``: a bare UUID parsed from message text must be
  ownership-verified before it is promoted into ``current_project_id`` /
  ``page_context``.
* L1 -- ``_sanitize_messages``: an AIMessage tool_call with no usable id
  (missing, or a duplicate another message already answered) must be
  stripped from the message's ``tool_calls``, not merely left unanswered.
* L4 -- ``_build_llm``'s ``_LLM_CACHE``: rotating the configured API key
  must miss the cache and build a fresh client.
"""

from __future__ import annotations

import functools
import sys
import types
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Iterator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent import _nodes_rag
from src.services.agent.graph import _sanitize_messages, rag_node
from src.services.do_kb.models import Chunk, RetrieveResult

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# M2 -- ownership-check exception must not widen DO KB scope to org-wide
# ---------------------------------------------------------------------------


@pytest.fixture
def kb_cfg() -> MagicMock:
    cfg = MagicMock()
    cfg.DO_KB_PRIMARY_READ = True
    cfg.DO_KB_RETRIEVE_TIMEOUT_SECONDS = 5.0
    return cfg


def _make_kb_session(
    org: MagicMock,
    *,
    execute_side_effect: Optional[BaseException] = None,
    execute_result: Any = None,
) -> MagicMock:
    """AsyncSession-shaped mock: ``.get`` resolves the org (KB lookup),
    ``.execute`` drives the ownership-check query inside
    ``_user_owns_project`` -- the same session both go through, mirroring
    the single ``tool_session()`` opened by ``_try_primary_do_kb_read_impl``.
    """
    session = MagicMock()
    session.get = AsyncMock(return_value=org)
    if execute_side_effect is not None:
        session.execute = AsyncMock(side_effect=execute_side_effect)
    else:
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = execute_result
        session.execute = AsyncMock(return_value=exec_result)
    return session


@asynccontextmanager
async def _session_ctx(session: MagicMock) -> AsyncIterator[MagicMock]:
    yield session


def _one_chunk_client() -> MagicMock:
    client = MagicMock()
    client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[Chunk(text="hi", score=0.9, document_id="doc-1", metadata={})],
            total=1,
        )
    )
    return client


async def _resolve_asserting_org_wide(
    *, chunks: list[Any], org_id: Any, session: Any, project_id: Optional[str]
) -> tuple[dict[str, Any], list[Any]]:
    assert project_id is None  # scope dropped to org-wide -- control assertion
    return ({}, chunks)


@pytest.mark.asyncio
async def test_unverifiable_ownership_aborts_primary_read(kb_cfg: MagicMock) -> None:
    """M2 bug: a DB error inside the ownership check must abort the primary
    read (return None so the caller falls back to hybrid search) instead of
    falling through to an org-wide DO KB read.

    Pre-fix, ``_user_owns_project`` collapsed the DB error into ``False``
    ("not owned"), the caller dropped ``scoped_project_id`` to ``None``, and
    ``resolve_and_filter_chunks`` WAS awaited with ``project_id=None`` --
    an org-wide read triggered by a transient outage, not a real ownership
    decision.
    """
    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    org = MagicMock()
    org.do_kb_uuid = "kb-1"

    session = _make_kb_session(org, execute_side_effect=RuntimeError("db down"))
    mock_resolve = AsyncMock(return_value=({}, []))

    with (
        patch("src.core.config.settings", kb_cfg),
        patch(
            "src.core.database.AsyncSessionLocal",
            functools.partial(_session_ctx, session),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=_one_chunk_client()),
        patch("src.services.do_kb.resolve.resolve_and_filter_chunks", mock_resolve),
    ):
        result = await _nodes_rag._try_primary_do_kb_read_impl(
            "q", user_id, org_id, project_id=project_id
        )

    assert result is None
    mock_resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_not_owned_still_drops_scope_org_wide(
    kb_cfg: MagicMock,
) -> None:
    """Control: a definitive 'not owned' (query ran, no matching row) is
    unchanged -- still drops scope and reads org-wide. Only the
    unverifiable case above is newly aborted."""
    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    org = MagicMock()
    org.do_kb_uuid = "kb-1"

    session = _make_kb_session(org, execute_result=None)  # no matching row

    with (
        patch("src.core.config.settings", kb_cfg),
        patch(
            "src.core.database.AsyncSessionLocal",
            functools.partial(_session_ctx, session),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=_one_chunk_client()),
        patch(
            "src.services.do_kb.resolve.resolve_and_filter_chunks",
            _resolve_asserting_org_wide,
        ),
    ):
        result = await _nodes_rag._try_primary_do_kb_read_impl(
            "q", user_id, org_id, project_id=project_id
        )

    assert result is not None and len(result) == 1


# ---------------------------------------------------------------------------
# M3 -- a bare UUID extracted from message text must be ownership-verified
# before it is promoted into current_project_id / page_context
# ---------------------------------------------------------------------------

_PASTED_UUID = "5ed25258-5ad2-4b06-9678-4a4abe5ecac1"
_PASTED_UUID_QUERY = f"Please check on the status of reference id {_PASTED_UUID} today"


def _rag_state(query: str) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=query)],
        "page_context": {},
        "current_project_id": None,
    }


@asynccontextmanager
async def _noop_tool_session() -> AsyncIterator[MagicMock]:
    yield MagicMock()


@asynccontextmanager
async def _failing_tool_session() -> AsyncIterator[MagicMock]:
    """A session that cannot be acquired — pool exhausted / DB down."""
    raise RuntimeError("QueuePool limit of size 5 overflow 10 reached")
    yield MagicMock()  # pragma: no cover — unreachable, keeps this a generator


@pytest.mark.asyncio
async def test_unacquirable_session_does_not_abort_the_turn() -> None:
    """The M3 gate must fail closed, not fail loudly.

    ``_user_owns_project`` converts its own failures into ``None``, but it
    never runs if the session cannot be acquired. Unguarded, that raises
    straight out of ``rag_node`` — which has no handler — so ``_RETRY_POLICY``
    burns three attempts and the turn dies, all because a check whose only
    power is to WITHHOLD a promotion could not run. The turn must proceed
    with the id simply not promoted.
    """
    user_id = str(uuid.uuid4())

    with patch("src.services.agent.tool_session.tool_session", _failing_tool_session):
        result = await rag_node(
            _rag_state(_PASTED_UUID_QUERY),
            config={"configurable": {"user_id": user_id}},
        )

    assert result.get("current_project_id") is None
    assert result.get("page_context", {}).get("type") != "project"


@pytest.mark.asyncio
async def test_unowned_extracted_uuid_not_promoted() -> None:
    """M3 bug: a bare UUID pasted into message text (could be a document
    id, a run id, or another org member's project link -- not necessarily
    a genuine ``/projects/<uuid>`` paste) must not be promoted into
    ``current_project_id`` / ``page_context`` without an ownership check.

    Pre-fix, ``rag_node`` promoted ANY extracted UUID unconditionally, so
    both assertions below fail against unmodified code.
    """
    user_id = str(uuid.uuid4())

    with (
        patch(
            "src.services.agent._nodes_rag._user_owns_project",
            new=AsyncMock(return_value=False),
        ),
        patch("src.services.agent.tool_session.tool_session", _noop_tool_session),
    ):
        result = await rag_node(
            _rag_state(_PASTED_UUID_QUERY),
            config={"configurable": {"user_id": user_id}},
        )

    assert result.get("current_project_id") is None
    assert result.get("page_context", {}).get("type") != "project"


@pytest.mark.asyncio
async def test_owned_extracted_uuid_still_promotes() -> None:
    """Control: an owned UUID still promotes into current_project_id and
    forces page_context.type='project' -- unchanged for the verified-owned
    case; only the unverified case above is newly gated."""
    user_id = str(uuid.uuid4())

    with (
        patch(
            "src.services.agent._nodes_rag._user_owns_project",
            new=AsyncMock(return_value=True),
        ),
        patch("src.services.agent.tool_session.tool_session", _noop_tool_session),
        patch(
            "src.services.agent._nodes_rag._try_primary_do_kb_read",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await rag_node(
            _rag_state(_PASTED_UUID_QUERY),
            config={"configurable": {"user_id": user_id}},
        )

    assert result.get("current_project_id") == _PASTED_UUID
    assert result["page_context"]["type"] == "project"
    assert result["page_context"]["project_id"] == _PASTED_UUID


# ---------------------------------------------------------------------------
# L1 -- sanitizer must strip (not just skip) an unanswerable tool_call
# ---------------------------------------------------------------------------


def test_sanitizer_strips_id_less_tool_call() -> None:
    """An id-less tool_call gets no ToolMessage (nothing to address) -- it
    must be removed from the AIMessage's ``tool_calls`` too, or the message
    still violates "every tool_call gets a reply" on the next LLM call
    (OpenAI 400). Pre-fix, ``rebuilt_ai.tool_calls`` still contains the
    id-less entry.
    """
    ai = AIMessage(content="", tool_calls=[{"id": "", "name": "noop", "args": {}}])
    out = _sanitize_messages([ai, HumanMessage(content="hi")])

    rebuilt_ai = next(m for m in out if isinstance(m, AIMessage))
    assert rebuilt_ai.tool_calls == []


def test_sanitizer_strips_duplicate_tool_call_id() -> None:
    """Two AIMessages sharing a tool_call_id: only the first gets the
    (single) ToolMessage; the second's duplicate entry must be stripped,
    not left dangling unanswered. Pre-fix, ``ais[1].tool_calls`` still
    contains the duplicate entry.
    """
    ai1 = AIMessage(content="", tool_calls=[{"id": "dup", "name": "noop", "args": {}}])
    ai2 = AIMessage(content="", tool_calls=[{"id": "dup", "name": "noop", "args": {}}])
    out = _sanitize_messages([ai1, ai2])

    ais = [m for m in out if isinstance(m, AIMessage)]
    assert len(ais) == 2
    assert ais[0].tool_calls[0]["id"] == "dup"
    assert ais[1].tool_calls == []


# ---------------------------------------------------------------------------
# L4 -- _LLM_CACHE must miss on credential rotation
# ---------------------------------------------------------------------------


def _make_langchain_openai_mock() -> types.ModuleType:
    mock_module = types.ModuleType("langchain_openai")
    # side_effect (not a fixed return_value) so each call yields a distinct
    # object -- otherwise a cache-miss rebuild and a cache-hit reuse would
    # be indistinguishable by identity (both would be the mock's singleton
    # .return_value).
    setattr(
        mock_module,
        "ChatOpenAI",
        MagicMock(side_effect=lambda **kwargs: MagicMock()),
    )
    setattr(
        mock_module,
        "AzureChatOpenAI",
        MagicMock(side_effect=lambda **kwargs: MagicMock()),
    )
    return mock_module


def _set_chat_settings(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    """Set the Azure chat-related settings on the shared settings instance."""
    from src.services.agent import graph as graph_module

    settings = graph_module.get_settings()
    defaults: dict[str, Any] = {
        "AZURE_OPENAI_ENDPOINT": None,
        "AZURE_OPENAI_API_KEY": None,
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
        "AZURE_OPENAI_DEPLOYMENT_NAME": None,
        "AZURE_OPENAI_CHAT_ENDPOINT": (
            "https://example.cognitiveservices.azure.com/openai/v1/"
        ),
        "AZURE_OPENAI_CHAT_API_KEY": "chat-key",
        "AZURE_OPENAI_CHAT_API_VERSION": "2024-12-01-preview",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "model-router",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(settings, key, value, raising=False)


@pytest.fixture
def clean_llm_caches() -> Iterator[None]:
    """Clear every LLM cache around the test, not just before it.

    These caches are module globals keyed on settings that other test modules
    (e.g. ``test_agent_build_llm.py``) also build against. Clearing only on
    entry leaves this test's MagicMock clients sitting in those globals for
    whoever runs next, making their correctness depend on each of them
    clearing first. Clearing on exit too keeps the leak from ever escaping.
    """
    from src.services.agent import graph as graph_module
    from src.services.agent import llm_factory

    def _clear() -> None:
        graph_module._LLM_CACHE.clear()
        llm_factory.reset_llm_caches()

    _clear()
    try:
        yield
    finally:
        _clear()


def test_llm_cache_misses_on_credential_rotation(
    monkeypatch: pytest.MonkeyPatch, clean_llm_caches: None
) -> None:
    """L4 bug: the cache key omitted credentials, so rotating
    ``AZURE_OPENAI_CHAT_API_KEY`` kept serving the OLD (dead-key) client
    until process restart. The key must include a credential fingerprint
    so rotation naturally misses the cache and builds a fresh client.
    """
    from src.services.agent import graph as graph_module

    _set_chat_settings(monkeypatch)
    mock_lc = _make_langchain_openai_mock()

    with patch.dict(sys.modules, {"langchain_openai": mock_lc}):
        first = graph_module._build_llm()
        _set_chat_settings(monkeypatch, AZURE_OPENAI_CHAT_API_KEY="rotated-key")
        second = graph_module._build_llm()

    assert first is not second


def test_factory_llm_caches_miss_on_credential_rotation(
    monkeypatch: pytest.MonkeyPatch, clean_llm_caches: None
) -> None:
    """The same rotation must invalidate the llm_factory caches too.

    ``_LLM_CACHE`` only backs ``llm_node``. The classifier, reflection,
    compactor, synthesis and fast-path clients come from these three caches,
    so keying only the first one would leave most of the agent authenticating
    with the dead key after a rotation.
    """
    from src.services.agent import llm_factory

    _set_chat_settings(monkeypatch)
    mock_lc = _make_langchain_openai_mock()

    with patch.dict(sys.modules, {"langchain_openai": mock_lc}):
        first_light = llm_factory.build_lightweight_llm()
        first_synth = llm_factory.build_synthesis_llm()
        first_fast = llm_factory.build_fast_path_llm()

        # Same credentials -> same cached instances (the cache still works).
        assert llm_factory.build_lightweight_llm() is first_light

        _set_chat_settings(monkeypatch, AZURE_OPENAI_CHAT_API_KEY="rotated-key")

        assert llm_factory.build_lightweight_llm() is not first_light
        assert llm_factory.build_synthesis_llm() is not first_synth
        assert llm_factory.build_fast_path_llm() is not first_fast
