"""Regression: extract_text_content Celery task awaits the async extractor.

process_text_extraction is async; the task called it without asyncio.run, so
`result` was a coroutine and `result["text_content"]` raised
"'coroutine' object is not subscriptable" — the task failed on every document.
This drives the task with a mocked async pipeline and asserts it completes.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
def test_extract_text_content_runs_async_extractor():
    from src.tasks.processing_tasks import extract_text_content

    job = MagicMock()
    document = SimpleNamespace(
        id="doc-1",
        content_text=None,
        content_summary=None,
        add_metadata=MagicMock(),
    )

    db = MagicMock()
    # First .first() → job, second → document.
    db.query.return_value.filter.return_value.first.side_effect = [job, document]

    pipeline = MagicMock()
    pipeline.process_text_extraction = AsyncMock(
        return_value={
            "text_content": "real extracted text",
            "summary": "sum",
            "word_count": 3,
            "character_count": 19,
        }
    )

    job.parameters = {"document_id": "doc-1"}

    with (
        patch("src.tasks.processing_tasks.SessionLocal", return_value=db),
        patch("src.tasks.processing_tasks.ProcessingPipeline", return_value=pipeline),
    ):
        result = extract_text_content.run("job-1")

    pipeline.process_text_extraction.assert_awaited_once()
    assert document.content_text == "real extracted text"
    assert result["text_content"] == "real extracted text"
    job.complete_job.assert_called_once()
    job.fail_job.assert_not_called()
