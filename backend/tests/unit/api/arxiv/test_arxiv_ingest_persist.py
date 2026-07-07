"""_process_arxiv_ingestion must persist papers and stamp the caller's org.

Two bugs this pins:
1. ingest_papers returns SimpleDocument objects (attributes, no .get); the old
   doc.get(...) raised AttributeError, swallowed by the outer except -> nothing
   persisted. Attribute access must work.
2. organization_id must come from the authenticated user (threaded param), not a
   doc field / "" default (which fails the NOT NULL FK).
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.api.arxiv import core

# Import before any test stubs out `src.core.database` (via monkeypatch): the
# ingest path lazily imports this module, whose top-level needs get_db_sync
# from the real database module. Caching it here keeps the stub harmless.
from src.services.search.fulltext_search_service import fulltext_search_service


class _FakeDoc:
    """Mirrors SimpleDocument: attributes only, no .get()."""

    def __init__(self):
        self.title = "A Paper"
        self.filename = "2401.00001.pdf"
        self.file_size_bytes = 123
        self.mime_type = "application/pdf"
        self.document_type = "PDF"
        self.content_text = "body"
        self.document_metadata = {"pdf_path": "/scratch/2401.00001.pdf"}


def _patch_pipeline(monkeypatch, documents):
    # get_db_session -> async generator yielding a fake db
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()  # search_vector UPDATE runs through here

    async def _fake_get_db_session():
        yield db

    fake_db_mod = SimpleNamespace(get_db_session=_fake_get_db_session)
    monkeypatch.setitem(sys.modules, "src.core.database", fake_db_mod)

    # ArXivIngestionService async context manager
    svc = MagicMock()
    svc.search_papers = AsyncMock(return_value=[{"id": "x"}])
    svc.ingest_papers = AsyncMock(return_value=documents)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=svc)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(core, "ArXivIngestionService", MagicMock(return_value=cm))

    # capture Document kwargs; give each a fake id so post-flush id access works
    captured = []

    def _make_doc(**kw):
        captured.append(kw)
        return SimpleNamespace(id=f"doc-{len(captured)}", **kw)

    monkeypatch.setattr(core, "Document", _make_doc)
    return db, captured


async def test_persists_with_caller_org_and_attribute_access(monkeypatch):
    db, captured = _patch_pipeline(monkeypatch, [_FakeDoc()])
    await core._process_arxiv_ingestion(
        paper_ids=["2401.00001"],
        user_id="user-1",
        organization_id="org-A",
        download_pdfs=False,
        extract_content=True,
        batch_size=1,
    )
    # Document was built (no AttributeError) and committed
    assert len(captured) == 1
    db.commit.assert_awaited_once()
    kw = captured[0]
    assert kw["organization_id"] == "org-A"  # threaded, not ""
    assert kw["uploaded_by_user_id"] == "user-1"
    assert kw["title"] == "A Paper"
    assert kw["file_path"] == "/scratch/2401.00001.pdf"  # from metadata pdf_path
    assert kw["is_public"] is False


async def test_org_never_read_from_doc(monkeypatch):
    # even if a doc carried an organization_id attribute, the caller's org wins
    d = _FakeDoc()
    d.organization_id = "org-EVIL"
    _, captured = _patch_pipeline(monkeypatch, [d])
    await core._process_arxiv_ingestion(
        paper_ids=["p"],
        user_id="u",
        organization_id="org-A",
        download_pdfs=False,
        extract_content=False,
        batch_size=1,
    )
    assert captured[0]["organization_id"] == "org-A"


async def test_one_bad_paper_does_not_abort_batch(monkeypatch):
    good = _FakeDoc()
    bad = object()  # no attributes -> getattr fallbacks, but force a failure:
    # make Document raise for the bad one via a metadata that isn't a dict
    bad = _FakeDoc()
    bad.document_metadata = "not-a-dict"  # .get on str -> AttributeError inside try
    db, captured = _patch_pipeline(monkeypatch, [bad, good])
    await core._process_arxiv_ingestion(
        paper_ids=["p"],
        user_id="u",
        organization_id="org-A",
        download_pdfs=False,
        extract_content=False,
        batch_size=2,
    )
    # good one still persisted + committed despite the bad one
    assert any(k["title"] == "A Paper" for k in captured)
    db.commit.assert_awaited_once()


async def test_builds_search_vector_before_commit(monkeypatch):
    """Persisted arXiv docs land COMPLETED, so search_vector must be built or
    they are permanently invisible to fulltext/RAG (NULL tsvector never
    matches). The updater runs on the same session before commit."""
    db, captured = _patch_pipeline(monkeypatch, [_FakeDoc(), _FakeDoc()])

    called = {}

    async def _fake_update(document_ids, session):
        called["ids"] = list(document_ids)
        called["session"] = session

    from src.services.search.fulltext_search_service import fulltext_search_service

    monkeypatch.setattr(
        fulltext_search_service,
        "async_update_document_search_vectors",
        _fake_update,
    )

    await core._process_arxiv_ingestion(
        paper_ids=["a", "b"],
        user_id="u",
        organization_id="org-A",
        download_pdfs=False,
        extract_content=True,
        batch_size=2,
    )

    assert called.get("ids") == ["doc-1", "doc-2"]
    assert called.get("session") is db
    db.commit.assert_awaited_once()
