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
    ), patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=None)
    ), patch.object(service, "extract_from_pdf", AsyncMock(return_value=None)):
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
        document_id=document_id,
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


# ============================================================================
# PDF extraction tests
# ============================================================================


def _make_mock_fitz_doc(
    metadata: dict | None = None,
    first_page_text: str = "",
) -> MagicMock:
    """Create a mock fitz document with configurable metadata and page text."""
    doc = MagicMock()
    doc.metadata = metadata or {}
    doc.__len__ = MagicMock(return_value=1)
    page = MagicMock()
    page.get_text.return_value = first_page_text
    doc.__getitem__ = MagicMock(return_value=page)
    doc.close = MagicMock()
    return doc


@pytest.mark.asyncio
async def test_extract_from_pdf_extracts_metadata() -> None:
    """PDF extraction should read title, authors, year, DOI from PDF metadata."""
    document_id = uuid4()
    db = AsyncMock()
    service = CitationExtractionService(db)

    document = MagicMock()
    document.id = document_id
    document.title = "DB Title"
    document.file_path = "/data/uploads/paper.pdf"

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = document
    db.execute = AsyncMock(return_value=query_result)

    mock_doc = _make_mock_fitz_doc(
        metadata={
            "title": "Attention Is All You Need",
            "author": "Vaswani, Ashish; Shazeer, Noam",
            "creationDate": "D:20170612120000",
        },
        first_page_text="Abstract\nhttps://doi.org/10.5555/3295222.3295349\narXiv:1706.03762v7",
    )

    mock_fitz_module = MagicMock()
    mock_fitz_module.open.return_value = mock_doc

    with patch.dict("sys.modules", {"fitz": mock_fitz_module}):
        citation = await service.extract_from_pdf(document_id)

    assert citation is not None
    assert citation.document_title == "Attention Is All You Need"
    assert citation.authors == ["Vaswani", "Ashish", "Shazeer", "Noam"]
    assert citation.year == 2017
    assert citation.doi == "10.5555/3295222.3295349"
    assert citation.arxiv_id == "1706.03762v7"
    assert citation.metadata_source == "pdf"
    assert citation.needs_review is True


@pytest.mark.asyncio
async def test_extract_from_pdf_returns_none_on_missing_document() -> None:
    """PDF extraction should return None when document not found in DB."""
    document_id = uuid4()
    db = AsyncMock()
    service = CitationExtractionService(db)

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=query_result)

    mock_fitz_module = MagicMock()
    with patch.dict("sys.modules", {"fitz": mock_fitz_module}):
        citation = await service.extract_from_pdf(document_id)

    assert citation is None


@pytest.mark.asyncio
async def test_extract_from_pdf_returns_none_on_fitz_error() -> None:
    """PDF extraction should return None when fitz.open raises."""
    document_id = uuid4()
    db = AsyncMock()
    service = CitationExtractionService(db)

    document = MagicMock()
    document.id = document_id
    document.title = "Some Paper"
    document.file_path = "/data/uploads/corrupted.pdf"

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = document
    db.execute = AsyncMock(return_value=query_result)

    mock_fitz_module = MagicMock()
    mock_fitz_module.open.side_effect = RuntimeError("corrupted PDF")

    with patch.dict("sys.modules", {"fitz": mock_fitz_module}):
        citation = await service.extract_from_pdf(document_id)

    assert citation is None


@pytest.mark.asyncio
async def test_extract_hybrid_auto_tries_pdf_before_manual() -> None:
    """AUTO strategy should try PDF extraction after CrossRef fails, before manual."""
    document_id = uuid4()
    service = CitationExtractionService(AsyncMock())
    pdf_citation = CitationCreate(
        document_title="PDF Extracted Title",
        metadata_source="pdf",
        needs_review=True,
    )

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=None)
    ), patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=None)
    ), patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=None)
    ), patch.object(
        service, "extract_from_pdf", AsyncMock(return_value=pdf_citation)
    ) as pdf_mock:
        citation, source = await service.extract_hybrid(
            arxiv_id="2301.07041",
            title="Some Paper",
            strategy="auto",
            document_id=document_id,
        )

    assert citation is not None
    assert source == "pdf"
    assert citation.document_title == "PDF Extracted Title"
    pdf_mock.assert_awaited_once_with(document_id)


@pytest.mark.asyncio
async def test_extract_hybrid_pdf_strategy() -> None:
    """Dedicated PDF strategy should call only extract_from_pdf."""
    document_id = uuid4()
    service = CitationExtractionService(AsyncMock())
    pdf_citation = CitationCreate(
        document_title="PDF Only",
        metadata_source="pdf",
        needs_review=True,
    )

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=None)
    ) as arxiv_mock, patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=None)
    ) as semsch_mock, patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=None)
    ) as crossref_mock, patch.object(
        service, "extract_from_pdf", AsyncMock(return_value=pdf_citation)
    ) as pdf_mock:
        citation, source = await service.extract_hybrid(
            title="Anything",
            strategy="pdf",
            document_id=document_id,
        )

    assert citation is not None
    assert source == "pdf"
    arxiv_mock.assert_not_awaited()
    semsch_mock.assert_not_awaited()
    crossref_mock.assert_not_awaited()
    pdf_mock.assert_awaited_once_with(document_id)
