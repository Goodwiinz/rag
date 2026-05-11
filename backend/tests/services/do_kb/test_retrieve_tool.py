"""Tests for the do_kb_retrieve agent tool.

Asserts: schema present in AGENT_TOOLS, empty-KB path returns empty list
without calling client, populated-KB returns parsed chunks, errors are
swallowed and surfaced as `error` field.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.agent.tools_impl import AGENT_TOOLS, _tool_do_kb_retrieve
from src.services.do_kb.models import Chunk, RetrieveResult


@pytest.mark.unit
def test_schema_registered():
    names = {t["function"]["name"] for t in AGENT_TOOLS}
    assert "do_kb_retrieve" in names


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_empty_when_disabled(monkeypatch):
    fake_settings = MagicMock()
    fake_settings.DO_KB_ENABLED = False
    monkeypatch.setattr("src.api.agent.tools_impl.settings", fake_settings, raising=False)

    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()
    result = await _tool_do_kb_retrieve(
        {"query": "anything", "top_k": 4}, db, user
    )
    assert result["chunks"] == []
    assert result["total"] == 0
    assert result.get("reason") == "disabled"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_empty_when_org_has_no_kb():
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    db.get = AsyncMock(return_value=MagicMock(do_kb_uuid=None))

    with patch(
        "src.core.config.settings",
        MagicMock(DO_KB_ENABLED=True),
    ), patch(
        "src.services.do_kb.get_do_kb_client",
    ) as mock_factory:
        result = await _tool_do_kb_retrieve(
            {"query": "anything", "top_k": 4}, db, user
        )
        mock_factory.assert_not_called()

    assert result["chunks"] == []
    assert result.get("reason") == "not_provisioned"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_happy_path_returns_chunks():
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)
    # Document lookup for title resolution — return empty rows, the helper
    # falls back to storage-key id and (c.metadata or {}).get("title").
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[
                Chunk(text="hello", score=0.9, document_id="doc-1", metadata={"k": "v"}),
                Chunk(text="world", score=0.5, document_id="doc-2", metadata={}),
            ],
            total=2,
        )
    )

    with patch(
        "src.core.config.settings",
        MagicMock(DO_KB_ENABLED=True),
    ), patch(
        "src.services.do_kb.get_do_kb_client", return_value=fake_client
    ):
        result = await _tool_do_kb_retrieve(
            {"query": "hello", "top_k": 5}, db, user
        )

    assert result["total"] == 2
    assert result["source"] == "do_kb"
    assert result["chunks"][0]["text"] == "hello"
    # Title resolution had no DB match → falls back to storage-key id.
    assert result["chunks"][0]["document_id"] == "doc-1"
    fake_client.retrieve.assert_awaited_once_with(
        kb_uuid="kb-1", query="hello", top_k=5
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_failure_returns_error_not_raise():
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "src.core.config.settings",
        MagicMock(DO_KB_ENABLED=True),
    ), patch(
        "src.services.do_kb.get_do_kb_client", return_value=fake_client
    ):
        result = await _tool_do_kb_retrieve(
            {"query": "x", "top_k": 3}, db, user
        )

    assert result["chunks"] == []
    assert "error" in result
    assert result["source"] == "do_kb"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_clamps_top_k():
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(chunks=[], total=0)
    )

    with patch(
        "src.core.config.settings",
        MagicMock(DO_KB_ENABLED=True),
    ), patch(
        "src.services.do_kb.get_do_kb_client", return_value=fake_client
    ):
        await _tool_do_kb_retrieve(
            {"query": "x", "top_k": 9999}, db, user
        )

    args = fake_client.retrieve.await_args
    assert args.kwargs["top_k"] == 20


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_query_rejected():
    user = MagicMock()
    user.organization_id = "org-1"
    result = await _tool_do_kb_retrieve({"query": "  "}, MagicMock(), user)
    assert "error" in result
    assert result["chunks"] == []
