"""Regression: content-hash de-duplication must be scoped to the caller's org.

The upload dedup query previously filtered only on checksum_sha256 + is_deleted
with NO organization_id, and the 409 echoed the matching document's
title/filename/id. That (a) disclosed another tenant's document metadata to any
user who uploaded matching content, and (b) wrongly blocked two orgs from each
holding the same common file. The fix routes all three storage paths through
_find_org_duplicate (org-scoped) and returns a generic 409 detail.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from src.services.documents.enhanced_file_service import EnhancedFileService


def _service_with_mock_db():
    # Bypass __init__ (it touches the filesystem); we only exercise the query.
    svc = object.__new__(EnhancedFileService)
    svc.db = MagicMock()
    return svc


@pytest.mark.unit
def test_dedup_query_is_org_scoped():
    svc = _service_with_mock_db()
    q = svc.db.query.return_value
    q.filter.return_value.first.return_value = "EXISTING_DOC"

    org_id = uuid.uuid4()
    result = svc._find_org_duplicate("deadbeef", org_id)

    assert result == "EXISTING_DOC"
    # The (first) dedup query must constrain BOTH the content hash AND the org.
    clauses = [str(c) for c in q.filter.call_args.args]
    assert any("checksum_sha256" in c for c in clauses)
    assert any(
        "organization_id" in c for c in clauses
    ), "dedup query is not org-scoped → cross-tenant leak: " + repr(clauses)


@pytest.mark.unit
def test_metadata_fallback_is_also_org_scoped():
    svc = _service_with_mock_db()
    q = svc.db.query.return_value
    # First (checksum) query misses, legacy metadata.file_hash query hits.
    q.filter.return_value.first.side_effect = [None, "META_DOC"]

    org_id = uuid.uuid4()
    result = svc._find_org_duplicate("deadbeef", org_id)

    assert result == "META_DOC"
    # call_args reflects the LAST .filter() — the metadata fallback — which must
    # ALSO carry the org scope.
    clauses = [str(c) for c in q.filter.call_args.args]
    assert any("organization_id" in c for c in clauses)


@pytest.mark.unit
def test_duplicate_detail_discloses_no_other_document_metadata():
    detail = EnhancedFileService._DUPLICATE_DETAIL
    lowered = detail.lower()
    # Static message — must not interpolate another row's title/filename/id.
    assert "{" not in detail and "}" not in detail
    assert "id:" not in lowered
    assert "title" not in lowered and "filename" not in lowered
    assert "workspace" in lowered
