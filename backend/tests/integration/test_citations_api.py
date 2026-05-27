"""
Integration tests for Citations API.

Tests the actual API endpoints through the FastAPI test client with
a real in-memory SQLite database, mocked auth, and mocked external
services (Semantic Scholar, CrossRef, ArXiv).
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Citation, Document
from src.models.document import DocumentType
from src.shared.research_schemas import CitationCreate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sample_document(test_db: AsyncSession, test_user) -> Document:
    """Create a sample document with ArXiv metadata for citation tests."""
    doc = Document(
        id=uuid4(),
        title="Attention Is All You Need",
        filename="attention.pdf",
        file_path="/data/uploads/attention.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        document_type=DocumentType.PDF,
        uploaded_by_user_id=test_user.id,
        organization_id=test_user.organization_id,
        is_public=True,
        document_metadata={
            "arxiv_id": "1706.03762",
            "doi": "10.5555/3295222.3295349",
            "title": "Attention Is All You Need",
        },
    )
    test_db.add(doc)
    await test_db.commit()
    await test_db.refresh(doc)
    return doc


@pytest_asyncio.fixture
async def sample_citations(test_db: AsyncSession, sample_document: Document):
    """Create a few citations linked to the sample document."""
    citations = []
    for i, (title, source) in enumerate(
        [
            ("BERT: Pre-training of Deep Bidirectional Transformers", "semantic_scholar"),
            ("GPT-4 Technical Report", "arxiv"),
            ("Incomplete Paper", "manual"),
        ]
    ):
        c = Citation(
            id=uuid4(),
            document_id=sample_document.id,
            document_title=title,
            authors=["Author A", "Author B"] if i < 2 else None,
            year=2023 - i if i < 2 else None,
            venue="NeurIPS" if i == 0 else None,
            doi=f"10.1000/paper{i}" if i == 0 else None,
            arxiv_id=f"230{i}.0000{i}" if i == 1 else None,
            metadata_source=source,
            needs_review=(i == 2),
        )
        test_db.add(c)
        citations.append(c)

    await test_db.commit()
    for c in citations:
        await test_db.refresh(c)
    return citations


# ===========================================================================
# POST /api/v1/citations (create)
# ===========================================================================


class TestCreateCitation:
    """Tests for the create citation endpoint."""

    @pytest.mark.asyncio
    async def test_create_citation_returns_201(self, async_client, sample_document):
        response = await async_client.post(
            "/api/v1/citations",
            json={
                "document_id": str(sample_document.id),
                "document_title": "New Citation",
                "authors": ["Alice Smith"],
                "year": 2024,
                "metadata_source": "manual",
                "needs_review": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data.get("documentTitle") == "New Citation" or data.get("document_title") == "New Citation"

    @pytest.mark.asyncio
    async def test_create_citation_persists_to_db(
        self, async_client, sample_document, test_db
    ):
        await async_client.post(
            "/api/v1/citations",
            json={
                "document_id": str(sample_document.id),
                "document_title": "Persisted Citation",
                "metadata_source": "manual",
            },
        )

        result = await test_db.execute(
            select(Citation).where(Citation.document_title == "Persisted Citation")
        )
        citation = result.scalar_one_or_none()
        assert citation is not None


# ===========================================================================
# GET /api/v1/citations (list)
# ===========================================================================


class TestListCitations:
    """Tests for the list citations endpoint."""

    @pytest.mark.asyncio
    async def test_list_returns_200(self, async_client, sample_citations):
        response = await async_client.get("/api/v1/citations")

        assert response.status_code == 200
        data = response.json()
        assert "citations" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_filter_by_document_id(
        self, async_client, sample_citations, sample_document
    ):
        response = await async_client.get(
            "/api/v1/citations",
            params={"document_id": str(sample_document.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_filter_by_needs_review(self, async_client, sample_citations):
        response = await async_client.get(
            "/api/v1/citations",
            params={"needs_review": True},
        )

        assert response.status_code == 200
        data = response.json()
        for citation in data["citations"]:
            assert citation.get("needsReview", citation.get("needs_review")) is True


# ===========================================================================
# GET /api/v1/citations/{id} (get single)
# ===========================================================================


class TestGetCitation:
    """Tests for the get single citation endpoint."""

    @pytest.mark.asyncio
    async def test_get_existing_citation(self, async_client, sample_citations):
        citation_id = str(sample_citations[0].id)
        response = await async_client.get(f"/api/v1/citations/{citation_id}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_nonexistent_citation_returns_404(self, async_client):
        fake_id = str(uuid4())
        response = await async_client.get(f"/api/v1/citations/{fake_id}")

        assert response.status_code == 404


# ===========================================================================
# POST /api/v1/citations/extract
# ===========================================================================


class TestExtractCitation:
    """Tests for the citation extraction endpoint."""

    @pytest.mark.asyncio
    async def test_extract_requires_at_least_one_identifier(self, async_client):
        response = await async_client.post(
            "/api/v1/citations/extract",
            json={},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_extract_with_mocked_service(
        self, async_client, sample_document
    ):
        mock_citation = CitationCreate(
            document_title="Extracted Paper",
            authors=["Mocked Author"],
            year=2024,
            arxiv_id="2401.00001",
            metadata_source="arxiv",
            needs_review=False,
        )

        with patch(
            "src.api.research.citations.CitationExtractionService"
        ) as MockService:
            instance = MockService.return_value
            instance.extract_for_document = AsyncMock(
                return_value=(mock_citation, "arxiv")
            )
            instance.extract_hybrid = AsyncMock(
                return_value=(mock_citation, "arxiv")
            )

            response = await async_client.post(
                "/api/v1/citations/extract",
                json={
                    "document_id": str(sample_document.id),
                    "strategy": "arxiv",
                },
            )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_extract_with_title_lookup(self, async_client):
        mock_citation = CitationCreate(
            document_title="Title Lookup Paper",
            metadata_source="semantic_scholar",
            needs_review=False,
        )

        with patch(
            "src.api.research.citations.CitationExtractionService"
        ) as MockService:
            instance = MockService.return_value
            instance.extract_hybrid = AsyncMock(
                return_value=(mock_citation, "semantic_scholar")
            )

            response = await async_client.post(
                "/api/v1/citations/extract",
                json={"title": "Title Lookup Paper"},
            )

        assert response.status_code == 201


# ===========================================================================
# POST /api/v1/citations/lookup
# ===========================================================================


class TestLookupCitation:
    """Tests for the citation lookup endpoint (no persistence)."""

    @pytest.mark.asyncio
    async def test_lookup_requires_identifier(self, async_client):
        response = await async_client.post(
            "/api/v1/citations/lookup",
            json={},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_lookup_returns_citation_without_persistence(
        self, async_client, test_db
    ):
        mock_citation = CitationCreate(
            document_title="Lookup Only Paper",
            metadata_source="crossref",
            needs_review=False,
        )

        with patch(
            "src.api.research.citations.CitationExtractionService"
        ) as MockService:
            instance = MockService.return_value
            instance.extract_hybrid = AsyncMock(
                return_value=(mock_citation, "crossref")
            )

            response = await async_client.post(
                "/api/v1/citations/lookup",
                json={"doi": "10.1000/test"},
            )

        assert response.status_code == 200

        # Verify NOT persisted
        result = await test_db.execute(
            select(Citation).where(
                Citation.document_title == "Lookup Only Paper"
            )
        )
        assert result.scalar_one_or_none() is None


# ===========================================================================
# POST /api/v1/citations/export
# ===========================================================================


class TestExportBibliography:
    """Tests for the bibliography export endpoint."""

    @pytest.mark.asyncio
    async def test_export_requires_ids_or_project(self, async_client):
        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "bibtex"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_export_bibtex_by_citation_ids(
        self, async_client, sample_citations
    ):
        ids = [str(c.id) for c in sample_citations[:2]]

        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "bibtex", "citation_ids": ids},
        )

        assert response.status_code == 200
        body = response.text
        assert "@" in body  # BibTeX marker

    @pytest.mark.asyncio
    async def test_export_ieee_format(self, async_client, sample_citations):
        ids = [str(c.id) for c in sample_citations[:1]]

        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "ieee", "citation_ids": ids},
        )

        assert response.status_code == 200
        assert "[1]" in response.text

    @pytest.mark.asyncio
    async def test_export_apa_format(self, async_client, sample_citations):
        ids = [str(c.id) for c in sample_citations[:1]]

        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "apa", "citation_ids": ids},
        )

        assert response.status_code == 200
        assert "(2023)" in response.text

    @pytest.mark.asyncio
    async def test_export_mla_format(self, async_client, sample_citations):
        ids = [str(c.id) for c in sample_citations[:1]]

        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "mla", "citation_ids": ids},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_unsupported_format_returns_400(
        self, async_client, sample_citations
    ):
        ids = [str(c.id) for c in sample_citations[:1]]

        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "chicago", "citation_ids": ids},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_export_nonexistent_citations_returns_404(self, async_client):
        fake_ids = [str(uuid4()), str(uuid4())]

        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "bibtex", "citation_ids": fake_ids},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_export_bibtex_content_disposition(
        self, async_client, sample_citations
    ):
        ids = [str(c.id) for c in sample_citations[:1]]

        response = await async_client.post(
            "/api/v1/citations/export",
            json={"format": "bibtex", "citation_ids": ids},
        )

        assert response.status_code == 200
        content_disp = response.headers.get("content-disposition", "")
        assert "bibliography.bib" in content_disp
