"""R2-M22: bulk_ingest_with_kg called ArXivIngestionService.ingest_papers with
an extract_entities kwarg the method doesn't accept (no **kwargs either) ->
TypeError -> 500 on every request. Entity extraction already happens via the
kg_integration.process_paper_kg_integration call right after; the fix drops
the bogus kwarg.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.arxiv.arxiv_knowledge_graph import (
    BulkIngestionRequest,
    bulk_ingest_with_kg,
)
from src.services.arxiv.arxiv_service import ArXivIngestionService

pytestmark = pytest.mark.unit


def test_ingest_papers_signature_has_no_extract_entities_kwarg():
    """Guards the underlying contract: if this ever regains extract_entities,
    the call site is free to pass it again, but not silently drop it."""
    sig = inspect.signature(ArXivIngestionService.ingest_papers)
    assert "extract_entities" not in sig.parameters
    assert not any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )


@pytest.mark.asyncio
async def test_bulk_ingest_route_does_not_raise_typeerror(monkeypatch):
    paper = {
        "id": "2401.00001v1",
        "title": "A Title",
        "abstract": "Abstract text.",
        "authors": ["Ada"],
        "categories": ["cs.AI"],
        "primary_category": "cs.AI",
    }

    arxiv_service = MagicMock()
    arxiv_service.search_papers = AsyncMock(return_value=[paper])
    arxiv_service.ingest_papers = AsyncMock(return_value=[MagicMock()])

    kg_integration = MagicMock()
    kg_integration.process_paper_kg_integration = AsyncMock(return_value={})

    current_user = {"organization_id": "org-1"}

    result = await bulk_ingest_with_kg(
        request=BulkIngestionRequest(query="cat:cs.AI", create_kg_entries=True),
        current_user=current_user,
        arxiv_service=arxiv_service,
        kg_integration=kg_integration,
    )

    assert result["status"] == "success"
    arxiv_service.ingest_papers.assert_awaited_once()
    _, kwargs = arxiv_service.ingest_papers.call_args
    assert "extract_entities" not in kwargs
