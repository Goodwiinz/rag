"""Pins for audit round-2 fixes on ArXivChangeTracker / bulk-ingest route.

R2-H1: process_paper_kg_integration must be called with the tenant's
organization_id, both from _ingest_new_paper and _update_knowledge_graph —
otherwise entities MERGE into the shared ""-org KG partition.

R2-H3: an abstract-only revision must land "abstract" in fields_changed so
_update_existing_paper's {"title","abstract"} gate actually fires and the
content_text / search vector get updated.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.arxiv import arxiv_change_tracker as tracker_module
from src.services.arxiv.arxiv_change_tracker import ArXivChangeTracker

pytestmark = pytest.mark.unit

ORG = "org-1"


def _paper(paper_id="2401.00001v1", title="A Title", abstract="Original abstract."):
    return {
        "id": paper_id,
        "title": title,
        "abstract": abstract,
        "authors": ["Ada"],
        "categories": ["cs.AI"],
        "primary_category": "cs.AI",
    }


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ArXivChangeTracker()


@pytest.fixture
def stub_session(monkeypatch):
    db = MagicMock()

    @asynccontextmanager
    async def _fake_session():
        yield db

    monkeypatch.setattr(tracker_module, "get_async_session", _fake_session)
    return db


def _stub_kg_integration(monkeypatch):
    """Patch ArXivKnowledgeGraphIntegration with a mock we can assert calls on."""
    kg = MagicMock()
    kg.process_paper_kg_integration = AsyncMock(return_value={"entities": []})
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=kg)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(
        tracker_module, "ArXivKnowledgeGraphIntegration", MagicMock(return_value=cm)
    )
    return kg


def test_abstract_only_change_is_detected(tracker):
    """R2-H3: changing only the abstract must appear in fields_changed."""
    seed = tracker.detect_changes([_paper()], ORG)
    assert [c.change_type for c in seed] == ["new"]

    updated = _paper(abstract="A materially different abstract.")
    changes = tracker.detect_changes([updated], ORG)

    assert len(changes) == 1
    assert changes[0].change_type == "updated"
    assert "abstract" in changes[0].fields_changed


@pytest.mark.asyncio
async def test_abstract_change_triggers_content_update(
    tracker, stub_session, monkeypatch
):
    """R2-H3: fields_changed=["abstract"] must reach _update_existing_paper's
    content-write gate (doc.content_text updated + search vectors refreshed)."""
    doc = MagicMock()
    doc.document_metadata = {}
    result = MagicMock()
    result.scalar_one_or_none.return_value = doc
    stub_session.execute = AsyncMock(return_value=result)
    stub_session.commit = AsyncMock()

    fulltext_mod = MagicMock()
    fulltext_mod.fulltext_search_service.async_update_document_search_vectors = (
        AsyncMock()
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "src.services.search.fulltext_search_service",
        fulltext_mod,
    )

    updated = _paper(abstract="A materially different abstract.")
    await tracker._update_existing_paper(stub_session, updated, ["abstract"], ORG)

    assert doc.content_text == "A materially different abstract."
    fulltext_mod.fulltext_search_service.async_update_document_search_vectors.assert_awaited_once()
    stub_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_new_paper_forwards_organization_id(tracker, monkeypatch):
    """R2-H1: _ingest_new_paper must pass organization_id to the KG call so
    entities don't MERGE into the shared ""-org partition."""
    kg = _stub_kg_integration(monkeypatch)

    persisted = MagicMock()
    persisted.document_ids = ["doc-1"]
    monkeypatch.setattr(
        "src.services.arxiv.persistence.persist_arxiv_documents",
        AsyncMock(return_value=persisted),
    )

    await tracker._ingest_new_paper(_paper(), ORG, user_id=None, update_kg=True)

    kg.process_paper_kg_integration.assert_awaited_once()
    _, kwargs = kg.process_paper_kg_integration.call_args
    assert kwargs.get("organization_id") == ORG


@pytest.mark.asyncio
async def test_apply_changes_update_forwards_organization_id(
    tracker, stub_session, monkeypatch
):
    """R2-H1: the 'updated' path in apply_changes must thread organization_id
    through to _update_knowledge_graph -> process_paper_kg_integration."""
    kg = _stub_kg_integration(monkeypatch)

    seed = tracker.detect_changes([_paper()], ORG)
    monkeypatch.setattr(
        tracker, "_fetch_paper_details", AsyncMock(return_value=_paper())
    )
    monkeypatch.setattr(tracker, "_ingest_new_paper", AsyncMock())
    await tracker.apply_changes(seed, ORG, update_kg=False)

    updated_paper = _paper(title="A New Title")
    changes = tracker.detect_changes([updated_paper], ORG)
    monkeypatch.setattr(
        tracker, "_fetch_paper_details", AsyncMock(return_value=updated_paper)
    )
    monkeypatch.setattr(tracker, "_update_existing_paper", AsyncMock())

    await tracker.apply_changes(changes, ORG, update_kg=True)

    kg.process_paper_kg_integration.assert_awaited_once()
    _, kwargs = kg.process_paper_kg_integration.call_args
    assert kwargs.get("organization_id") == ORG
