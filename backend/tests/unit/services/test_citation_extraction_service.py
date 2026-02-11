"""Unit tests for citation extraction service behavior."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.services.research.citation_extraction_service import CitationExtractionService
from src.shared.research_schemas import CitationCreate, CitationResponse


@pytest.mark.asyncio
async def test_extract_hybrid_uses_manual_fallback_when_sources_fail() -> None:
    """AUTO strategy should fall back to manual citation when lookups fail."""
    service = CitationExtractionService(AsyncMock())

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=None)
    ), patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=None)
    ), patch.object(service, "extract_from_crossref", AsyncMock(return_value=None)):
        citation, source = await service.extract_hybrid(
            arxiv_id="2301.07041",
            title="Sample Research Paper",
            strategy="auto",
        )

    assert citation is not None
    assert source == "manual"
    assert citation.document_title == "Sample Research Paper"
    assert citation.needs_review is True


@pytest.mark.asyncio
async def test_extract_hybrid_honors_crossref_strategy() -> None:
    """CROSSREF strategy should call only crossref lookup."""
    service = CitationExtractionService(AsyncMock())
    crossref_citation = CitationCreate(
        document_title="CrossRef Paper",
        doi="10.1000/example",
        metadata_source="crossref",
    )

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=None)
    ) as arxiv_mock, patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=None)
    ) as semsch_mock, patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=crossref_citation)
    ) as crossref_mock:
        citation, source = await service.extract_hybrid(
            doi="10.1000/example",
            strategy="crossref",
        )

    assert citation is not None
    assert source == "crossref"
    arxiv_mock.assert_not_awaited()
    semsch_mock.assert_not_awaited()
    crossref_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_for_document_uses_metadata_identifiers() -> None:
    """Document extraction should infer DOI/title from document metadata."""
    document_id = uuid4()
    db = AsyncMock()
    service = CitationExtractionService(db)

    document = MagicMock()
    document.id = document_id
    document.title = "Metadata Paper"
    document.document_metadata = {"doi": "https://doi.org/10.1234/abcd"}

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = document
    db.execute = AsyncMock(return_value=query_result)

    extracted = CitationCreate(
        document_title="Metadata Paper",
        doi="10.1234/abcd",
        metadata_source="crossref",
    )

    with patch.object(
        service, "extract_hybrid", AsyncMock(return_value=(extracted, "crossref"))
    ) as extract_mock:
        citation, source = await service.extract_for_document(
            document_id=document_id,
            strategy="auto",
        )

    assert citation is not None
    assert source == "crossref"
    assert citation.document_id == document_id
    extract_mock.assert_awaited_once_with(
        arxiv_id=None,
        doi="10.1234/abcd",
        title="Metadata Paper",
        strategy="auto",
    )


def test_citation_author_normalization_accepts_dicts_and_strings() -> None:
    """Citation schemas should normalize mixed author payloads to string names."""
    create_model = CitationCreate(
        document_title="Normalization Test",
        authors=[
            {"name": "Alice Doe"},
            {"given": "Bob", "family": "Smith"},
            "Carol Lane",
        ],
    )
    assert create_model.authors == ["Alice Doe", "Bob Smith", "Carol Lane"]

    response_model = CitationResponse.model_validate(
        {
            "id": UUID("00000000-0000-0000-0000-000000000001"),
            "document_title": "Normalization Test",
            "document_type": "paper",
            "authors": [{"name": "Alice Doe"}],
            "score": 0.0,
            "metadata_source": "manual",
            "needs_review": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    assert response_model.authors == ["Alice Doe"]
