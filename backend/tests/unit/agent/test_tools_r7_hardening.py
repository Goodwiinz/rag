"""Audit R7-B — tool-surface hardening.

R7-M4  every tool result is size-bounded at the ``execute_tool`` choke point.
R7-L8  the title fallback in ``_resolve_document_id`` never guesses.
R7-L9  a DESTRUCTIVE tool never takes the CONTEXT_FREE fast path.
R7-L10 ``_tool_execute_code`` fails closed without a thread_id.
R7-L11 arXiv ids are validated before they reach the PDF URL builder.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agent import tools_impl
from src.services.agent.tools_impl import _MAX_TOOL_RESULT_BYTES, execute_tool

# ---------------------------------------------------------------------------
# R7-M4 — result size cap
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_huge_tool_result_is_truncated(monkeypatch):
    async def _fake_dispatch(*args, **kwargs):
        return {
            "status": "success",
            "stdout": "A" * (50 * 1024 * 1024),
            "stderr": "B" * 4096,
            "exit_code": 0,
        }

    monkeypatch.setattr(tools_impl, "_dispatch_tool", _fake_dispatch)

    result = await execute_tool(
        "execute_code", {}, db=MagicMock(), current_user=MagicMock()
    )

    assert result["truncated"] is True
    assert len(json.dumps(result, default=str)) <= _MAX_TOOL_RESULT_BYTES
    assert "truncated" in result["stdout"]
    assert result["exit_code"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_small_tool_result_is_untouched(monkeypatch):
    payload = {"status": "success", "stdout": "hello", "exit_code": 0}

    async def _fake_dispatch(*args, **kwargs):
        return dict(payload)

    monkeypatch.setattr(tools_impl, "_dispatch_tool", _fake_dispatch)

    result = await execute_tool(
        "execute_code", {}, db=MagicMock(), current_user=MagicMock()
    )

    assert result == payload


@pytest.mark.unit
@pytest.mark.asyncio
async def test_many_medium_fields_are_bounded(monkeypatch):
    async def _fake_dispatch(*args, **kwargs):
        return {
            "results": [{"title": "T" * 5000, "url": "u" * 5000} for _ in range(20)]
        }

    monkeypatch.setattr(tools_impl, "_dispatch_tool", _fake_dispatch)

    result = await execute_tool(
        "search_external_database", {}, db=MagicMock(), current_user=MagicMock()
    )

    assert result["truncated"] is True
    assert len(json.dumps(result, default=str)) <= _MAX_TOOL_RESULT_BYTES
    assert len(result["results"]) == 20


# ---------------------------------------------------------------------------
# R7-L9 — destructive tools are never CONTEXT_FREE
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_tool_is_both_context_free_and_destructive():
    from src.services.agent.tool_registry import ToolPolicyTag
    from src.services.agent.tools import TOOL_REGISTRY

    offenders = [
        d.name
        for d in TOOL_REGISTRY.descriptors
        if ToolPolicyTag.CONTEXT_FREE in d.policy_tags
        and ToolPolicyTag.DESTRUCTIVE in d.policy_tags
    ]
    assert offenders == [], offenders


@pytest.mark.unit
@pytest.mark.asyncio
async def test_forget_memory_requires_a_resolved_user(monkeypatch):
    called = False

    async def _boom(**kwargs):
        nonlocal called
        called = True
        return {"status": "completed"}

    monkeypatch.setattr(tools_impl, "_tool_forget_memory", _boom)

    result = await tools_impl._dispatch_tool(
        "forget_memory",
        {"query": "everything"},
        user_id="00000000-0000-0000-0000-000000000001",
        db=MagicMock(),
        current_user=None,
    )

    assert "error" in result
    assert called is False


# ---------------------------------------------------------------------------
# R7-L10 — execute_code needs a thread id
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_code_rejects_empty_thread_id():
    result = await tools_impl._tool_execute_code(
        {"code": "print(1)"}, thread_id="", current_user=MagicMock()
    )
    assert "error" in result
    assert "thread" in result["error"].lower()


# ---------------------------------------------------------------------------
# R7-L11 — arXiv id grammar
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "paper_id",
    ["2401.12345", "2401.1234", "2303.15563v2", "math/0309136", "math.GT/0309136v1"],
)
def test_valid_arxiv_ids_accepted(paper_id):
    from src.services.agent.tools import _reject_invalid_arxiv_ids

    assert _reject_invalid_arxiv_ids([paper_id]) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "paper_id",
    [
        "../../robots.txt?x=",
        "2401.12345/../../etc/passwd",
        "https://evil.example/x.pdf",
        "",
        "24.1",
        "2401.12345 2401.12346",
    ],
)
def test_invalid_arxiv_ids_rejected(paper_id):
    from src.services.agent.tools import _reject_invalid_arxiv_ids

    rejected = _reject_invalid_arxiv_ids([paper_id])
    assert rejected is not None and "error" in rejected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_arxiv_pdf_download_caps_read_size(tmp_path, monkeypatch):
    from src.services.arxiv import arxiv_service as svc

    class _Content:
        async def read(self, n=-1):
            # More than the cap allows; the caller must ask for a bounded read.
            assert n == svc._MAX_PDF_BYTES + 1
            return b"x" * n

    class _Response:
        content = _Content()

        def raise_for_status(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    session = MagicMock()
    session.get = MagicMock(return_value=_Response())

    service = svc.ArXivIngestionService.__new__(svc.ArXivIngestionService)
    service.session = session
    service.download_dir = tmp_path
    service.MAX_RETRIES = 1

    with pytest.raises(svc.IngestionError):
        await service.download_paper_pdf("2401.12345")


# ---------------------------------------------------------------------------
# R7-L8 — title fallback must not guess
# ---------------------------------------------------------------------------


def _db_returning(docs):
    async def _execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = docs
        result.scalar_one_or_none.return_value = None
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)
    return db


def _doc(title):
    doc = MagicMock()
    doc.title = title
    return doc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_title_fallback_exact_single_match_resolves():
    from src.services.agent.tool_helpers import _resolve_document_id

    doc = _doc("Attention Is All You Need")
    user = MagicMock()
    user.organization_id = "org-1"

    got = await _resolve_document_id(
        "attention is all you need", _db_returning([doc]), user
    )
    assert got is doc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_title_fallback_ambiguous_match_returns_none():
    from src.services.agent.tool_helpers import _resolve_document_id

    user = MagicMock()
    user.organization_id = "org-1"
    docs = [_doc("Report 2024"), _doc("Report 2024")]

    assert await _resolve_document_id("Report 2024", _db_returning(docs), user) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_title_fallback_substring_only_match_returns_none():
    from src.services.agent.tool_helpers import _resolve_document_id

    user = MagicMock()
    user.organization_id = "org-1"
    docs = [_doc("A Long Report About Transformers")]

    assert await _resolve_document_id("transformers", _db_returning(docs), user) is None
