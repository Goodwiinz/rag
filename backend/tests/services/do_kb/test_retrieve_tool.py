"""Tests for the do_kb_retrieve agent tool.

Asserts: schema present in AGENT_TOOLS, empty-KB path returns empty list
without calling client, populated-KB returns parsed chunks, errors are
swallowed and surfaced as `error` field.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent.tools_impl import AGENT_TOOLS, _tool_do_kb_retrieve
from src.services.do_kb.client import DOKnowledgeBaseError
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
    monkeypatch.setattr(
        "src.services.agent.tools_impl.settings", fake_settings, raising=False
    )

    user = MagicMock()
    user.organization_id = "org-1"
    db = MagicMock()
    result = await _tool_do_kb_retrieve({"query": "anything", "top_k": 4}, db, user)
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

    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch(
            "src.services.do_kb.get_do_kb_client",
        ) as mock_factory,
    ):
        result = await _tool_do_kb_retrieve({"query": "anything", "top_k": 4}, db, user)
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
    # Document lookup for title resolution returns no match. Unresolved
    # storage identifiers must not be exposed as citation IDs or titles.
    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[
                Chunk(
                    text="hello", score=0.9, document_id="doc-1", metadata={"k": "v"}
                ),
                Chunk(text="world", score=0.5, document_id="doc-2", metadata={}),
            ],
            total=2,
        )
    )

    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
    ):
        result = await _tool_do_kb_retrieve({"query": "hello", "top_k": 5}, db, user)

    assert result["total"] == 2
    assert result["source"] == "do_kb"
    assert result["chunks"][0]["text"] == "hello"
    # Title resolution had no DB match, so the raw storage id is omitted.
    assert result["chunks"][0]["document_id"] is None
    assert result["chunks"][0]["title"] == "Untitled"
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

    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 3}, db, user)

    assert result["chunks"] == []
    assert "error" in result
    assert result["source"] == "do_kb"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_404_logs_error_and_falls_back(caplog):
    """FIX A3: a 404 (KB deleted on DO's side) is a permanent failure — it must
    be logged distinctly at ERROR, not blended into WARNING transient noise.
    Still returns an empty result so the agent falls back cleanly."""
    import logging

    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        side_effect=DOKnowledgeBaseError("not found", status_code=404)
    )

    with (
        patch("src.core.config.settings", MagicMock(DO_KB_ENABLED=True)),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        caplog.at_level(logging.ERROR, logger="src.services.agent.tools_impl"),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 3}, db, user)

    # Fallback preserved: empty result, not a raise.
    assert result["chunks"] == []
    assert result["total"] == 0
    assert result["source"] == "do_kb"
    # The 404 was logged at ERROR level with a distinct message.
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("404" in r.getMessage() for r in error_records)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieve_transient_error_stays_warning(caplog):
    """A non-404 DOKnowledgeBaseError (transient) must NOT be logged at ERROR —
    it stays at WARNING so 404s remain distinguishable."""
    import logging

    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        side_effect=DOKnowledgeBaseError("upstream down", status_code=503)
    )

    with (
        patch("src.core.config.settings", MagicMock(DO_KB_ENABLED=True)),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        caplog.at_level(logging.WARNING, logger="src.services.agent.tools_impl"),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 3}, db, user)

    assert result["chunks"] == []
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not error_records  # no ERROR for a transient failure


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
    fake_client.retrieve = AsyncMock(return_value=RetrieveResult(chunks=[], total=0))

    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
    ):
        await _tool_do_kb_retrieve({"query": "x", "top_k": 9999}, db, user)

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


# -- Phase 2: project_id post-filter -----------------------------------------
# Trace 019e168a showed KB returning chunks from sibling projects because the
# KB is org-scoped. When `project_id` is supplied, drop chunks whose resolved
# document is not in the active project (via collection_documents).


@pytest.mark.unit
@pytest.mark.asyncio
async def test_project_id_filters_out_cross_project_chunks():
    import uuid

    user = MagicMock()
    user.organization_id = "org-1"

    in_project_doc_id = uuid.uuid4()
    out_of_project_doc_id = uuid.uuid4()
    pid = uuid.uuid4()

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    # First db.execute call resolves title_by_key (storage-key → UUID, title).
    # Second call resolves project membership (collection_documents).
    title_rows = [
        (in_project_doc_id, "in.pdf", "In-project doc"),
        (out_of_project_doc_id, "out.pdf", "Cross-project doc"),
    ]
    membership_rows = [(in_project_doc_id,)]

    title_result = MagicMock()
    title_result.__iter__ = lambda self: iter(title_rows)
    membership_result = MagicMock()
    membership_result.__iter__ = lambda self: iter(membership_rows)
    db.execute = AsyncMock(side_effect=[title_result, membership_result])

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[
                Chunk(text="in", score=0.9, document_id="in.pdf", metadata={}),
                Chunk(text="out", score=0.8, document_id="out.pdf", metadata={}),
            ],
            total=2,
        )
    )

    owned = MagicMock()
    owned.id = pid
    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        patch(
            "src.services.agent.tools_impl._verify_project_ownership",
            AsyncMock(return_value=owned),
        ),
    ):
        result = await _tool_do_kb_retrieve(
            {"query": "x", "top_k": 5, "project_id": str(pid)}, db, user
        )

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["text"] == "in"
    assert result["total"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_project_id_keeps_all_chunks():
    """Without project_id, all chunks pass through (legacy behavior)."""
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[
                Chunk(text="a", score=0.9, document_id="a.pdf", metadata={}),
                Chunk(text="b", score=0.5, document_id="b.pdf", metadata={}),
            ],
            total=2,
        )
    )

    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
    ):
        result = await _tool_do_kb_retrieve({"query": "x", "top_k": 5}, db, user)

    assert len(result["chunks"]) == 2
    assert result["total"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owned_project_id_with_unresolvable_chunks_returns_empty():
    """Owned project_id but no chunk resolves to a known document → empty.

    Once ownership is verified, the shared resolve_and_filter_chunks helper
    still returns an empty list when none of the retrieved chunks map to a
    document in the project, so unscoped content is never leaked.
    """
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    empty_rows = MagicMock()
    empty_rows.__iter__ = lambda self: iter([])
    db.execute = AsyncMock(return_value=empty_rows)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[Chunk(text="a", score=0.9, document_id="a.pdf", metadata={})],
            total=1,
        )
    )

    owned = MagicMock()
    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        patch(
            "src.services.agent.tools_impl._verify_project_ownership",
            AsyncMock(return_value=owned),
        ),
    ):
        result = await _tool_do_kb_retrieve(
            {
                "query": "x",
                "top_k": 5,
                "project_id": "11111111-1111-1111-1111-111111111111",
            },
            db,
            user,
        )

    # Unresolvable chunks + project_id → empty (no leaking unscoped content).
    assert len(result["chunks"]) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_project_id_not_owned_returns_access_denied():
    """A project_id the caller does not own must be rejected, not used as a
    filter — otherwise it leaks which org documents belong to that project
    (membership inference). Mirrors the sibling project tools' guard."""
    user = MagicMock()
    user.organization_id = "org-1"

    db = MagicMock()
    org_row = MagicMock()
    org_row.do_kb_uuid = "kb-1"
    db.get = AsyncMock(return_value=org_row)

    fake_client = MagicMock()
    fake_client.retrieve = AsyncMock(
        return_value=RetrieveResult(
            chunks=[Chunk(text="secret", score=0.9, document_id="x.pdf", metadata={})],
            total=1,
        )
    )

    with (
        patch(
            "src.core.config.settings",
            MagicMock(DO_KB_ENABLED=True),
        ),
        patch("src.services.do_kb.get_do_kb_client", return_value=fake_client),
        patch(
            "src.services.agent.tools_impl._verify_project_ownership",
            AsyncMock(return_value=None),  # not owned / not found
        ),
    ):
        result = await _tool_do_kb_retrieve(
            {"query": "x", "top_k": 5, "project_id": "someone-elses-project"},
            db,
            user,
        )

    assert result["chunks"] == []
    assert result["total"] == 0
    assert "access denied" in result.get("error", "").lower()
