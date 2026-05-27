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
    assert citation.authors == ["Vaswani, Ashish", "Shazeer, Noam"]
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


# ============================================================================
# Helper method tests: _normalize_arxiv_id
# ============================================================================


class TestNormalizeArxivId:
    """Tests for CitationExtractionService._normalize_arxiv_id."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2301.07041", "2301.07041"),
            ("  2301.07041  ", "2301.07041"),
            ("https://arxiv.org/abs/2301.07041", "2301.07041"),
            ("http://arxiv.org/abs/2301.07041", "2301.07041"),
            ("arXiv:2301.07041", "2301.07041"),
            ("arxiv:2301.07041v2", "2301.07041v2"),
            ("https://arxiv.org/abs/1706.03762v7", "1706.03762v7"),
        ],
    )
    def test_normalizes_various_formats(self, raw: str, expected: str) -> None:
        assert CitationExtractionService._normalize_arxiv_id(raw) == expected

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_returns_none_for_empty_values(self, value) -> None:
        assert CitationExtractionService._normalize_arxiv_id(value) is None


# ============================================================================
# Helper method tests: _extract_doi
# ============================================================================


class TestExtractDoi:
    """Tests for CitationExtractionService._extract_doi."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("10.1000/test.paper", "10.1000/test.paper"),
            ("https://doi.org/10.1000/test.paper", "10.1000/test.paper"),
            ("doi: 10.5555/3295222.3295349", "10.5555/3295222.3295349"),
            (
                "See paper at https://doi.org/10.1038/s41586-020-2012-7 for details.",
                "10.1038/s41586-020-2012-7",
            ),
            # Trailing punctuation stripped
            ("10.1000/example.", "10.1000/example"),
            ("10.1000/example,", "10.1000/example"),
            ("10.1000/example;", "10.1000/example"),
        ],
    )
    def test_extracts_doi_from_various_formats(self, raw: str, expected: str) -> None:
        assert CitationExtractionService._extract_doi(raw) == expected

    @pytest.mark.parametrize("value", [None, "", "no doi here", "just text"])
    def test_returns_none_when_no_doi_present(self, value) -> None:
        assert CitationExtractionService._extract_doi(value) is None


# ============================================================================
# Manual fallback tests
# ============================================================================


class TestManualFallback:
    """Tests for CitationExtractionService._manual_fallback."""

    def test_creates_citation_from_title(self) -> None:
        service = CitationExtractionService(AsyncMock())
        result = service._manual_fallback(title="My Paper")

        assert result is not None
        assert result.document_title == "My Paper"
        assert result.metadata_source == "manual"
        assert result.needs_review is True

    def test_creates_citation_from_arxiv_id_alone(self) -> None:
        service = CitationExtractionService(AsyncMock())
        result = service._manual_fallback(title=None, arxiv_id="2301.07041")

        assert result is not None
        assert result.arxiv_id == "2301.07041"
        assert result.document_title == "Untitled paper"

    def test_creates_citation_from_doi_alone(self) -> None:
        service = CitationExtractionService(AsyncMock())
        result = service._manual_fallback(
            title=None, doi="https://doi.org/10.1000/test"
        )

        assert result is not None
        assert result.doi == "10.1000/test"

    def test_returns_none_when_all_inputs_empty(self) -> None:
        service = CitationExtractionService(AsyncMock())
        result = service._manual_fallback(title="", arxiv_id=None, doi=None)

        assert result is None


# ============================================================================
# Strategy-specific extract_hybrid tests
# ============================================================================


@pytest.mark.asyncio
async def test_extract_hybrid_arxiv_strategy() -> None:
    """ARXIV strategy should call only arxiv lookup."""
    service = CitationExtractionService(AsyncMock())
    arxiv_citation = CitationCreate(
        document_title="ArXiv Paper",
        arxiv_id="2301.07041",
        metadata_source="arxiv",
    )

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=arxiv_citation)
    ) as arxiv_mock, patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=None)
    ) as semsch_mock, patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=None)
    ) as crossref_mock:
        citation, source = await service.extract_hybrid(
            arxiv_id="2301.07041",
            strategy="arxiv",
        )

    assert citation is not None
    assert source == "arxiv"
    arxiv_mock.assert_awaited_once()
    semsch_mock.assert_not_awaited()
    crossref_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_hybrid_semantic_scholar_strategy() -> None:
    """SEMANTIC_SCHOLAR strategy should call only Semantic Scholar lookup."""
    service = CitationExtractionService(AsyncMock())
    ss_citation = CitationCreate(
        document_title="SS Paper",
        metadata_source="semantic_scholar",
    )

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=None)
    ) as arxiv_mock, patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=ss_citation)
    ) as semsch_mock, patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=None)
    ) as crossref_mock:
        citation, source = await service.extract_hybrid(
            title="Some Paper",
            strategy="semantic_scholar",
        )

    assert citation is not None
    assert source == "semantic_scholar"
    arxiv_mock.assert_not_awaited()
    semsch_mock.assert_awaited_once()
    crossref_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_hybrid_manual_strategy() -> None:
    """MANUAL strategy should return a manual fallback citation directly."""
    service = CitationExtractionService(AsyncMock())

    citation, source = await service.extract_hybrid(
        title="Manual Entry Paper",
        strategy="manual",
    )

    assert citation is not None
    assert source == "manual"
    assert citation.needs_review is True
    assert citation.document_title == "Manual Entry Paper"


@pytest.mark.asyncio
async def test_extract_hybrid_invalid_strategy_falls_back_to_auto() -> None:
    """An unrecognized strategy should be treated as 'auto'."""
    service = CitationExtractionService(AsyncMock())

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=None)
    ), patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=None)
    ), patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=None)
    ), patch.object(service, "extract_from_pdf", AsyncMock(return_value=None)):
        citation, source = await service.extract_hybrid(
            title="Test",
            strategy="INVALID_STRATEGY",
        )

    # Falls through to manual in auto mode
    assert citation is not None
    assert source == "manual"


@pytest.mark.asyncio
async def test_extract_hybrid_auto_stops_at_first_success() -> None:
    """AUTO strategy should stop calling sources once one succeeds."""
    service = CitationExtractionService(AsyncMock())
    arxiv_citation = CitationCreate(
        document_title="Found via ArXiv",
        metadata_source="arxiv",
    )

    with patch.object(
        service, "extract_from_arxiv", AsyncMock(return_value=arxiv_citation)
    ), patch.object(
        service, "extract_from_semantic_scholar", AsyncMock(return_value=None)
    ) as semsch_mock, patch.object(
        service, "extract_from_crossref", AsyncMock(return_value=None)
    ) as crossref_mock:
        citation, source = await service.extract_hybrid(
            arxiv_id="2301.07041",
            strategy="auto",
        )

    assert source == "arxiv"
    # Subsequent sources should NOT be called
    semsch_mock.assert_not_awaited()
    crossref_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_hybrid_returns_none_when_nothing_available() -> None:
    """When no identifiers are provided, extract_hybrid returns None."""
    service = CitationExtractionService(AsyncMock())

    citation, source = await service.extract_hybrid(
        arxiv_id=None,
        doi=None,
        title=None,
        strategy="auto",
    )

    assert citation is None
    assert source == "none"


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
