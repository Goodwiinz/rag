"""apply_changes must not persist state for changes that failed to apply.

detect_changes stamps the new hash into per-org state BEFORE apply_changes
runs, and apply_changes ends with save_state() regardless of per-paper
failures. A transient fetch failure (arXiv 429 — Sentry
JAVASCRIPT-NEXTJS-48/49) therefore persisted the new hash with the paper
never ingested/updated, and the next scan saw "no change": the paper was
silently lost. These tests pin the revert path that makes the next scan
re-emit the change.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.arxiv import arxiv_change_tracker as tracker_module
from src.services.arxiv.arxiv_change_tracker import ArXivChangeTracker

pytestmark = pytest.mark.unit

ORG = "org-1"


def _paper(paper_id="2401.00001v1", title="A Title"):
    return {
        "id": paper_id,
        "title": title,
        "authors": ["Ada"],
        "categories": ["cs.AI"],
        "primary_category": "cs.AI",
    }


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    # state_file is cwd-relative ("data/arxiv_change_state.json")
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


@pytest.mark.asyncio
async def test_failed_new_paper_fetch_reverts_state(tracker, stub_session, monkeypatch):
    changes = tracker.detect_changes([_paper()], ORG)
    assert [c.change_type for c in changes] == ["new"]

    monkeypatch.setattr(
        tracker, "_fetch_paper_details", AsyncMock(return_value=None)
    )
    summary = await tracker.apply_changes(changes, ORG, update_kg=False)

    assert summary == {"new": 0, "updated": 0, "deleted": 0, "errors": 1}
    # State entry removed → next scan re-detects the paper as new.
    redetected = tracker.detect_changes([_paper()], ORG)
    assert [c.change_type for c in redetected] == ["new"]


@pytest.mark.asyncio
async def test_failed_update_fetch_restores_old_hash(
    tracker, stub_session, monkeypatch
):
    # Seed v1 successfully (fetch works, ingest stubbed).
    seed = tracker.detect_changes([_paper()], ORG)
    monkeypatch.setattr(
        tracker, "_fetch_paper_details", AsyncMock(return_value=_paper())
    )
    monkeypatch.setattr(tracker, "_ingest_new_paper", AsyncMock())
    await tracker.apply_changes(seed, ORG, update_kg=False)

    # v2 detected, but the apply-time fetch 429s.
    v2 = _paper(title="A Better Title")
    changes = tracker.detect_changes([v2], ORG)
    assert [c.change_type for c in changes] == ["updated"]
    monkeypatch.setattr(
        tracker, "_fetch_paper_details", AsyncMock(return_value=None)
    )
    summary = await tracker.apply_changes(changes, ORG, update_kg=False)

    assert summary["errors"] == 1
    # Old hash restored → next scan re-emits the update.
    redetected = tracker.detect_changes([v2], ORG)
    assert [c.change_type for c in redetected] == ["updated"]


@pytest.mark.asyncio
async def test_apply_exception_reverts_deleted_marker(
    tracker, stub_session, monkeypatch
):
    # Drive a paper to the deletion threshold.
    tracker.detect_changes([_paper()], ORG)
    deletion_changes = []
    for _ in range(tracker.DELETION_MISS_THRESHOLD):
        deletion_changes = tracker.detect_changes(
            [], ORG, tracked_categories={"cs.AI"}
        )
    assert [c.change_type for c in deletion_changes] == ["deleted"]

    monkeypatch.setattr(
        tracker, "_mark_paper_deleted", AsyncMock(side_effect=RuntimeError("db down"))
    )
    summary = await tracker.apply_changes(deletion_changes, ORG, update_kg=False)

    assert summary["errors"] == 1
    # "deleted" marker reverted; miss_count stays at threshold → re-emitted.
    redetected = tracker.detect_changes([], ORG, tracked_categories={"cs.AI"})
    assert [c.change_type for c in redetected] == ["deleted"]


@pytest.mark.asyncio
async def test_429_fetch_failure_logs_warning_not_error(tracker, monkeypatch, caplog):
    svc = MagicMock()
    svc.search_papers = AsyncMock(
        side_effect=Exception("ArXiv rate limited (HTTP 429). Try again in 60 seconds.")
    )
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=svc)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(
        tracker_module, "ArXivIngestionService", MagicMock(return_value=cm)
    )

    with caplog.at_level("WARNING", logger=tracker_module.logger.name):
        assert await tracker._fetch_paper_details("2401.00001v1") is None

    records = [r for r in caplog.records if "2401.00001v1" in r.message]
    assert records and all(r.levelname == "WARNING" for r in records)
