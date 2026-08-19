"""R4-L6 regression: ``BulkStatusRequest`` had no cap on ``document_ids``
(unbounded batch size) and defaulted ``include_jobs`` to ``True``, which
triggered a per-document jobs query in a loop -- N+1 (up to N round trips
per request, N unbounded). ``document_ids`` is now capped at 100,
``include_jobs`` defaults to ``False``, and when jobs are requested they're
fetched in a single ``.in_()`` query grouped in python.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.api.realtime.realtime_document_status import (
    BulkStatusRequest,
    get_bulk_realtime_status,
)

pytestmark = pytest.mark.unit


def _org() -> MagicMock:
    o = MagicMock()
    o.id = uuid.uuid4()
    return o


def test_document_ids_over_100_rejected() -> None:
    ids = [str(uuid.uuid4()) for _ in range(101)]
    with pytest.raises(ValidationError):
        BulkStatusRequest(document_ids=ids)


def test_document_ids_at_100_accepted() -> None:
    ids = [str(uuid.uuid4()) for _ in range(100)]
    req = BulkStatusRequest(document_ids=ids)
    assert len(req.document_ids) == 100


def test_include_jobs_defaults_false() -> None:
    req = BulkStatusRequest(document_ids=[str(uuid.uuid4())])
    assert req.include_jobs is False


def _make_document(doc_id: uuid.UUID) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.filename = "f.pdf"
    doc.title = "t"
    doc.document_type.value = "pdf"
    doc.processing_status.value = "indexed"
    doc.processing_started_at = None
    doc.processing_completed_at = None
    doc.processing_error = None
    doc.processing_retry_count = 0
    doc.updated_at.isoformat.return_value = "2026-01-01T00:00:00"
    return doc


def _make_job(document_id: uuid.UUID) -> MagicMock:
    job = MagicMock()
    job.id = uuid.uuid4()
    job.document_id = document_id
    job.job_type.value = "ingestion"
    job.status.value = "completed"
    job.progress_percentage = 100.0
    job.current_step = None
    return job


def test_include_jobs_uses_single_query_not_per_document() -> None:
    doc1_id, doc2_id = uuid.uuid4(), uuid.uuid4()
    doc1, doc2 = _make_document(doc1_id), _make_document(doc2_id)

    doc_result = MagicMock()
    doc_result.scalars.return_value.all.return_value = [doc1, doc2]

    jobs_result = MagicMock()
    jobs_result.scalars.return_value.all.return_value = [
        _make_job(doc1_id),
        _make_job(doc2_id),
    ]

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[doc_result, jobs_result])

    request = BulkStatusRequest(
        document_ids=[str(doc1_id), str(doc2_id)], include_jobs=True
    )

    resp = asyncio.run(
        get_bulk_realtime_status(
            request,
            current_user=MagicMock(),
            organization=_org(),
            session=session,
        )
    )

    # Exactly 2 queries total: the document lookup + ONE grouped jobs query,
    # never one jobs query per document.
    assert session.execute.await_count == 2
    assert len(resp["documents"][str(doc1_id)]["jobs"]) == 1
    assert len(resp["documents"][str(doc2_id)]["jobs"]) == 1


def test_include_jobs_false_skips_jobs_query_entirely() -> None:
    doc1_id = uuid.uuid4()
    doc1 = _make_document(doc1_id)

    doc_result = MagicMock()
    doc_result.scalars.return_value.all.return_value = [doc1]

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[doc_result])

    request = BulkStatusRequest(document_ids=[str(doc1_id)], include_jobs=False)

    resp = asyncio.run(
        get_bulk_realtime_status(
            request,
            current_user=MagicMock(),
            organization=_org(),
            session=session,
        )
    )

    assert session.execute.await_count == 1
    assert "jobs" not in resp["documents"][str(doc1_id)]
