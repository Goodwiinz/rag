"""Round-1 audit M7, M8, L7, L8, L9 — the @tool wrapper layer's contracts.

Each of these was a wrapper quietly rewriting the model's request into
something else: dropping ids past a cap while reporting success, downgrading a
rejected connector name to "search everything", and sharing one stateful
sandbox between conversations.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import Any, Dict
from uuid import uuid4

import pytest

from src.services.agent import tools as agent_tools


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ingest_refuses_over_cap_instead_of_truncating() -> None:
    """M8: 15 requested used to become 10 ingested, reported as '10 of 10'."""
    paper_ids = [f"2401.{i:05d}" for i in range(15)]

    result = await agent_tools.ingest_arxiv_papers.ainvoke({"paper_ids": paper_ids})

    assert "error" in result
    assert "15" in result["error"]
    assert str(agent_tools._MAX_INGEST_BATCH) in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_compare_cap_matches_the_impl_limit() -> None:
    """L7: wrapper capped at 10, impl rejected >5 — 6-10 was an error loop."""
    assert agent_tools._MAX_COMPARE_DOCUMENTS == 5

    result = await agent_tools.compare_documents.ainvoke(
        {"document_ids": [str(uuid4()) for _ in range(6)]}
    )

    assert "error" in result
    assert "5" in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bibliography_export_is_bounded() -> None:
    """L8: document_ids went through uncapped, producing an unbounded IN()."""
    result = await agent_tools.export_bibliography.ainvoke(
        {"document_ids": [str(uuid4()) for _ in range(51)]}
    )

    assert "error" in result
    # Must be the cap talking, not an incidental auth/context error.
    assert str(agent_tools._MAX_EXPORT_DOCUMENTS) in result["error"]
    assert "51" in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalid_connector_is_refused_not_fanned_out() -> None:
    """M7: a rejected name became 'unspecified' → ~250-connector burst."""
    result = await agent_tools.search_external_database.ainvoke(
        {"query": "aspirin", "connector": "pub med!"}
    )

    assert "error" in result
    assert "connector" in result["error"]

    domain_result = await agent_tools.list_external_databases.ainvoke(
        {"domain": "../../etc"}
    )
    assert "error" in domain_result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_valid_connector_still_reaches_the_impl(monkeypatch) -> None:
    """The M7 guard must not touch the legitimate path."""
    seen: Dict[str, Any] = {}

    async def _fake_impl(args: Dict[str, Any]) -> Dict[str, Any]:
        seen.update(args)
        return {"results": []}

    import src.services.agent.tools_impl as tools_impl

    monkeypatch.setattr(tools_impl, "_tool_search_external_database", _fake_impl)

    await agent_tools.search_external_database.ainvoke(
        {"query": "aspirin", "connector": "pubmed"}
    )

    assert seen["connector"] == "pubmed"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sandbox_key_never_falls_back_to_a_shared_literal(monkeypatch) -> None:
    """L9: no thread_id meant thread_id='default' — one sandbox for everyone."""
    user = SimpleNamespace(id=uuid4())
    seen: Dict[str, Any] = {}

    @contextlib.asynccontextmanager
    async def _fake_context(_config):
        yield (None, user, None)

    async def _fake_exec(_args, *, thread_id, current_user):
        seen["thread_id"] = thread_id
        return {"ok": True}

    import src.services.agent.tools_impl as tools_impl

    monkeypatch.setattr(agent_tools, "_tool_context", _fake_context)
    monkeypatch.setattr(tools_impl, "_tool_execute_code", _fake_exec)

    await agent_tools.execute_code.ainvoke({"code": "1+1", "description": "smoke"})

    assert seen["thread_id"] == f"user-{user.id}"
    assert seen["thread_id"] != "default"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sandbox_fails_closed_without_a_caller_identity(monkeypatch) -> None:
    """No thread_id and no user must refuse, not join the shared sandbox."""

    called: Dict[str, Any] = {}

    @contextlib.asynccontextmanager
    async def _fake_context(_config):
        yield (None, None, None)

    async def _fake_exec(_args, *, thread_id, current_user):
        called["thread_id"] = thread_id
        return {"ok": True}

    import src.services.agent.tools_impl as tools_impl

    monkeypatch.setattr(agent_tools, "_tool_context", _fake_context)
    monkeypatch.setattr(tools_impl, "_tool_execute_code", _fake_exec)

    result = await agent_tools.execute_code.ainvoke(
        {"code": "1+1", "description": "smoke"}
    )

    assert "error" in result
    # The sandbox must never have been opened at all.
    assert called == {}
