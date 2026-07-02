"""extract/lookup citation endpoints must verify document_id belongs to caller's org.

Both endpoints pass a client-supplied document_id to the extraction service,
which reads that document's metadata / PDF. Without an org check, org-A could
read org-B's document title / DOI / arXiv id (and PDF contents) by supplying
org-B's document uuid. create_citation already had this guard; extract/lookup
missed it. These tests pin the 404-on-foreign-doc behavior at the endpoint.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from src.api.research import citations as cit


def _db(doc_check_result):
    """AsyncSession whose execute(...).scalar_one_or_none() -> doc_check_result."""
    db = MagicMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = doc_check_result
    db.execute = AsyncMock(return_value=exec_result)
    return db


def _caller(org="org-A"):
    return SimpleNamespace(id="u1", organization_id=org)


@pytest.mark.parametrize("endpoint", [cit.extract_citation, cit.lookup_citation])
async def test_foreign_document_id_404(endpoint, monkeypatch):
    # extraction service must never be reached for a doc the caller doesn't own
    svc = MagicMock()
    svc.extract_for_document = AsyncMock(
        side_effect=AssertionError("extraction ran on unowned document")
    )
    monkeypatch.setattr(cit, "CitationExtractionService", MagicMock(return_value=svc))
    db = _db(None)  # org-scoped doc check finds nothing
    with pytest.raises(HTTPException) as ei:
        await endpoint(
            request=SimpleNamespace(
                document_id=uuid4(), arxiv_id=None, doi=None, title=None, strategy=None
            ),
            document_id=None,
            arxiv_id=None,
            doi=None,
            title=None,
            strategy="auto",
            current_user=_caller("org-A"),
            db=db,
        )
    assert ei.value.status_code == 404
    svc.extract_for_document.assert_not_awaited()
