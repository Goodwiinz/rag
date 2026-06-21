"""Regression: extract_entities task surfaces ExtractionResult.error.

A timeout that skips chunks sets ExtractionResult.error while still returning
the entities found so far. The task previously reported only entities_extracted,
hiding the partial extraction. It must surface the error in the job result.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
def test_extract_entities_reports_partial_on_extraction_error():
    from src.tasks.processing_tasks import extract_entities

    job = MagicMock()
    job.parameters = {"document_id": "doc-1"}
    document = SimpleNamespace(
        id="doc-1", content_text="some text", organization_id="org-1"
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [job, document]

    service = MagicMock()
    service.extract_entities = AsyncMock(
        return_value=SimpleNamespace(
            entities=[], relationships=[], error="timeout after 1/3 chunks"
        )
    )

    with (
        patch("src.tasks.processing_tasks.SessionLocal", return_value=db),
        patch(
            "src.tasks.processing_tasks.LLMEntityExtractionService",
            return_value=service,
        ),
    ):
        extract_entities.run("job-1")

    result = job.complete_job.call_args.kwargs["result"]
    assert result["partial"] is True
    assert result["extraction_error"] == "timeout after 1/3 chunks"
    assert result["entities_extracted"] == 0
