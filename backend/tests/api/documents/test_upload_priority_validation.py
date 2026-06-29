"""Regression: invalid processing_priority must 400 BEFORE the upload.

upload_single_document did `JobPriority[processing_priority.upper()]` only
AFTER file_service.upload_file had committed the Document + uploaded its
object. An unknown priority (client-supplied) raised KeyError → generic 500,
orphaning the object + row. Priority is now validated up front via
_resolve_job_priority, which 400s on an invalid value.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.documents.document_upload import _resolve_job_priority
from src.models.processing import JobPriority


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected",
    [
        ("normal", JobPriority.NORMAL),
        ("HIGH", JobPriority.HIGH),
        ("low", JobPriority.LOW),
        ("urgent", JobPriority.URGENT),
    ],
)
def test_valid_priority_resolves(value, expected):
    assert _resolve_job_priority(value) is expected


@pytest.mark.unit
@pytest.mark.parametrize("value", ["bogus", "", "URGENT!", "1"])
def test_invalid_priority_raises_400(value):
    with pytest.raises(HTTPException) as ei:
        _resolve_job_priority(value)
    assert ei.value.status_code == 400
    assert "processing_priority" in str(ei.value.detail)
