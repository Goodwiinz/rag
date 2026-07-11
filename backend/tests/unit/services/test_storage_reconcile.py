"""Report-only Spaces ⇄ Postgres storage reconciler (audit finding D6).

Lists an org's Spaces objects and diffs them against keys referenced by live
(non-deleted) rows: objects with no live referrer are orphans (LOGGED, never
deleted). These tests assert the diff spares every object a live document
references (the safety invariant) and reports exactly the leftovers of a
deleted document across all three object classes.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.documents import storage_reconcile as mod
from src.services.documents.storage_reconcile import (
    StorageReconcileReport,
    _classify_key,
    reconcile_all_orgs_storage,
    reconcile_org_storage,
)

pytestmark = pytest.mark.unit


def _scalar_result(items):
    r = MagicMock()
    r.scalars.return_value.all.return_value = list(items)
    return r


def _live_doc(org_id, doc_id, storage_path):
    doc = MagicMock()
    doc.organization_id = org_id
    doc.id = doc_id
    doc.storage_path = storage_path
    return doc


def _session(doc_rows, figure_metadata_rows):
    # _referenced_keys issues two queries: live Documents, then figure metadata.
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_result(doc_rows),
            _scalar_result(figure_metadata_rows),
        ]
    )
    return session


def _s3_helper(listing_by_prefix):
    helper = MagicMock()
    helper.list_objects = MagicMock(
        side_effect=lambda prefix: listing_by_prefix[prefix]
    )
    return helper


def test_reports_orphans_and_spares_referenced_objects():
    org = "org-1"
    # One live doc D1 (original + canonical .txt + one figure). D2 was deleted,
    # so its three objects still sit in the bucket with no live referrer.
    d1 = _live_doc(org, "d1", f"documents/{org}/d1/100_a.pdf")
    figure_meta = {"storage_key": f"figures/{org}/d1/figure-p1-x5.png"}
    session = _session([d1], [figure_meta])

    listing = {
        f"documents/{org}/": [
            f"documents/{org}/d1/100_a.pdf",  # D1 original (referenced)
            f"documents/{org}/d1.txt",  # D1 canonical (referenced)
            f"documents/{org}/d2/200_b.pdf",  # D2 original (orphan)
            f"documents/{org}/d2.txt",  # D2 canonical (orphan)
        ],
        f"images/{org}/": [],
        f"audio/{org}/": [],
        f"video/{org}/": [],
        f"figures/{org}/": [
            f"figures/{org}/d1/figure-p1-x5.png",  # D1 figure (referenced)
            f"figures/{org}/d2/figure-p1-x9.png",  # D2 figure (orphan)
        ],
    }
    helper = _s3_helper(listing)

    report = asyncio.run(reconcile_org_storage(session, org, s3_helper=helper))

    assert isinstance(report, StorageReconcileReport)
    assert report.listed_count == 6
    assert report.referenced_count == 3  # D1: original + canonical + figure
    assert report.orphan_keys == [
        f"documents/{org}/d2.txt",
        f"documents/{org}/d2/200_b.pdf",
        f"figures/{org}/d2/figure-p1-x9.png",
    ]
    assert report.orphan_count == 3
    # Safety invariant: no object a live document references is ever an orphan.
    for referenced in (
        f"documents/{org}/d1/100_a.pdf",
        f"documents/{org}/d1.txt",
        f"figures/{org}/d1/figure-p1-x5.png",
    ):
        assert referenced not in report.orphan_keys


def test_clean_when_every_object_is_referenced():
    org = "org-2"
    d1 = _live_doc(org, "d1", f"documents/{org}/d1/1_a.pdf")
    session = _session([d1], [])
    listing = {
        f"documents/{org}/": [f"documents/{org}/d1/1_a.pdf", f"documents/{org}/d1.txt"],
        f"images/{org}/": [],
        f"audio/{org}/": [],
        f"video/{org}/": [],
        f"figures/{org}/": [],
    }
    report = asyncio.run(
        reconcile_org_storage(session, org, s3_helper=_s3_helper(listing))
    )
    assert report.orphan_count == 0
    assert report.orphan_keys == []


def test_documents_without_storage_path_do_not_crash_or_false_reference():
    # A local-backend doc has storage_path=None; only its canonical .txt key is
    # derivable. Must not blow up, and None must never enter the referenced set.
    org = "org-3"
    d1 = _live_doc(org, "d1", None)
    session = _session([d1], [])
    listing = {
        f"documents/{org}/": [f"documents/{org}/d1.txt", f"documents/{org}/stray.bin"],
        f"images/{org}/": [],
        f"audio/{org}/": [],
        f"video/{org}/": [],
        f"figures/{org}/": [],
    }
    report = asyncio.run(
        reconcile_org_storage(session, org, s3_helper=_s3_helper(listing))
    )
    assert report.orphan_keys == [f"documents/{org}/stray.bin"]


def test_classify_key():
    assert _classify_key("figures/o/d/figure-p1-x5.png") == "figure"
    assert _classify_key("documents/o/d.txt") == "kb_text"
    assert _classify_key("documents/o/d/100_a.pdf") == "original"


def test_reconcile_all_orgs_is_failure_isolated(monkeypatch):
    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(["good", "bad"]))

    async def fake_reconcile(_session, org_id, *, s3_helper=None):
        if org_id == "bad":
            raise RuntimeError("spaces outage for this org")
        return StorageReconcileReport(
            organization_id=org_id, listed_count=0, referenced_count=0, orphan_keys=[]
        )

    monkeypatch.setattr(mod, "reconcile_org_storage", fake_reconcile)

    reports = asyncio.run(reconcile_all_orgs_storage(session, s3_helper=MagicMock()))

    # The bad org is logged + skipped; the good org's report still comes back.
    assert [r.organization_id for r in reports] == ["good"]
