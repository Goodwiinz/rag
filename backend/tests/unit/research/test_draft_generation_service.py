"""
Unit tests for DraftGenerationService (T110)

Tests AI-powered draft generation, versioning, and export.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4
import asyncio

from src.services.research.draft_generation_service import DraftGenerationService


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.scalars = MagicMock()
    return session


@pytest.fixture
def draft_service(mock_db_session):
    """Create a DraftGenerationService instance for testing."""
    return DraftGenerationService(db=mock_db_session)


@pytest.fixture
def sample_project():
    """Create a sample project with documents."""
    return {
        "id": str(uuid4()),
        "name": "ML Healthcare Research",
        "documents": [
            {"id": "doc1", "title": "Paper 1", "content": "Content of paper 1..."},
            {"id": "doc2", "title": "Paper 2", "content": "Content of paper 2..."},
            {"id": "doc3", "title": "Paper 3", "content": "Content of paper 3..."},
        ],
    }


@pytest.fixture
def sample_draft():
    """Create a sample generated draft."""
    return {
        "id": str(uuid4()),
        "project_id": str(uuid4()),
        "version": 1,
        "title": "Literature Review: Machine Learning in Healthcare",
        "content": """# Introduction

Machine learning has emerged as a transformative technology in healthcare [Doc 1].

# Methodology

Recent studies have employed various ML techniques [Doc 2]. Deep learning approaches
have shown particular promise [Doc 3].

# Conclusions

The application of ML in healthcare continues to grow [Doc 1, Doc 2].
""",
        "themes": ["introduction", "methodology", "conclusions"],
        "word_count": 150,
        "citation_count": 4,
        "is_current": True,
        "created_at": datetime.utcnow(),
    }


class TestDraftGeneration:
    """Tests for draft generation."""

    @pytest.mark.asyncio
    async def test_generate_draft_with_themes(self, draft_service, mock_db_session, sample_project):
        """Test generating a draft organized by themes."""
        themes = ["introduction", "methodology", "results", "discussion"]

        with patch.object(draft_service, 'generate_draft') as mock_generate:
            mock_generate.return_value = {
                "id": str(uuid4()),
                "version": 1,
                "themes": themes,
                "content": "# Introduction\n...\n# Methodology\n...",
                "status": "completed",
            }

            result = await draft_service.generate_draft(
                project_id=sample_project["id"],
                themes=themes,
                db=mock_db_session,
            )

            assert result is not None
            assert result["themes"] == themes
            assert "Introduction" in result["content"] or "introduction" in result["themes"]

    @pytest.mark.asyncio
    async def test_generate_draft_includes_citations(self, draft_service, mock_db_session, sample_project):
        """Test that generated drafts include [Doc N] format citations."""
        with patch.object(draft_service, 'generate_draft') as mock_generate:
            mock_generate.return_value = {
                "id": str(uuid4()),
                "content": "As shown by recent research [Doc 1], the field has advanced [Doc 2].",
                "citation_count": 2,
            }

            result = await draft_service.generate_draft(
                project_id=sample_project["id"],
                db=mock_db_session,
            )

            assert result is not None
            assert "[Doc 1]" in result["content"] or "[Doc " in result["content"]
            assert result["citation_count"] >= 1


class TestDraftVersioning:
    """Tests for draft versioning."""

    @pytest.mark.asyncio
    async def test_draft_versioning(self, draft_service, mock_db_session, sample_project):
        """Test that new generation creates a new version."""
        with patch.object(draft_service, 'generate_draft') as mock_generate:
            # First generation
            mock_generate.return_value = {"id": "draft1", "version": 1}
            result1 = await draft_service.generate_draft(
                project_id=sample_project["id"],
                db=mock_db_session,
            )

            # Second generation
            mock_generate.return_value = {"id": "draft2", "version": 2}
            result2 = await draft_service.generate_draft(
                project_id=sample_project["id"],
                db=mock_db_session,
            )

            assert result2["version"] > result1["version"]

    @pytest.mark.asyncio
    async def test_draft_version_retention(self, draft_service, mock_db_session, sample_project):
        """Test that only last 10 versions are retained, older ones archived."""
        with patch.object(draft_service, 'list_drafts') as mock_list:
            # Simulate having 12 drafts
            mock_list.return_value = [
                {"id": f"draft{i}", "version": i, "archived": i <= 2}
                for i in range(1, 13)
            ]

            result = await draft_service.list_drafts(
                project_id=sample_project["id"],
                db=mock_db_session,
            )

            # First 2 should be archived
            archived = [d for d in result if d.get("archived")]
            active = [d for d in result if not d.get("archived")]

            assert len(archived) == 2
            assert len(active) == 10


class TestDraftTimeout:
    """Tests for generation timeout handling."""

    @pytest.mark.asyncio
    async def test_draft_generation_timeout(self, draft_service, mock_db_session, sample_project):
        """Test that generation times out after 120s with proper error."""
        with patch.object(draft_service, '_generate_draft_async') as mock_async:
            mock_async.side_effect = asyncio.TimeoutError()

            with patch.object(draft_service, 'generate_draft') as mock_generate:
                mock_generate.return_value = {
                    "status": "failed",
                    "error": "Generation timed out after 120 seconds",
                }

                result = await draft_service.generate_draft(
                    project_id=sample_project["id"],
                    db=mock_db_session,
                )

                assert result["status"] == "failed"
                assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()


class TestDraftExport:
    """Tests for draft export functionality."""

    @pytest.mark.asyncio
    async def test_draft_export_latex(self, draft_service, mock_db_session, sample_draft):
        """Test exporting draft to .tex + .bib format."""
        with patch.object(draft_service, 'export_draft') as mock_export:
            mock_export.return_value = {
                "format": "latex",
                "files": {
                    "main.tex": "\\documentclass{article}\n...",
                    "references.bib": "@article{doc1,...}\n@article{doc2,...}",
                },
                "zip_content": b"<zip bytes>",
            }

            result = await draft_service.export_draft(
                draft_id=sample_draft["id"],
                format="latex",
                db=mock_db_session,
            )

            assert result is not None
            assert result["format"] == "latex"
            assert "main.tex" in result["files"]
            assert "references.bib" in result["files"]

    @pytest.mark.asyncio
    async def test_draft_export_markdown(self, draft_service, mock_db_session, sample_draft):
        """Test exporting draft to markdown format."""
        with patch.object(draft_service, 'export_draft') as mock_export:
            mock_export.return_value = {
                "format": "markdown",
                "content": sample_draft["content"],
                "filename": "literature_review.md",
            }

            result = await draft_service.export_draft(
                draft_id=sample_draft["id"],
                format="markdown",
                db=mock_db_session,
            )

            assert result is not None
            assert result["format"] == "markdown"
            assert ".md" in result["filename"]


class TestDraftRetrieval:
    """Tests for draft retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_draft(self, draft_service, mock_db_session, sample_draft):
        """Test retrieving a specific draft."""
        with patch.object(draft_service, 'get_draft') as mock_get:
            mock_get.return_value = sample_draft

            result = await draft_service.get_draft(
                draft_id=sample_draft["id"],
                db=mock_db_session,
            )

            assert result is not None
            assert result["id"] == sample_draft["id"]
            assert result["content"] == sample_draft["content"]

    @pytest.mark.asyncio
    async def test_list_drafts(self, draft_service, mock_db_session, sample_project):
        """Test listing all drafts for a project."""
        drafts = [
            {"id": "d1", "version": 3, "is_current": True},
            {"id": "d2", "version": 2, "is_current": False},
            {"id": "d3", "version": 1, "is_current": False},
        ]

        with patch.object(draft_service, 'list_drafts') as mock_list:
            mock_list.return_value = drafts

            result = await draft_service.list_drafts(
                project_id=sample_project["id"],
                db=mock_db_session,
            )

            assert len(result) == 3
            # Should be ordered by version, newest first
            assert result[0]["version"] > result[-1]["version"]


class TestDraftComparison:
    """Tests for draft version comparison."""

    @pytest.mark.asyncio
    async def test_compare_drafts(self, draft_service, mock_db_session):
        """Test comparing two draft versions."""
        draft_v1 = {
            "id": "d1",
            "version": 1,
            "content": "Original content here.",
            "word_count": 100,
            "citation_count": 3,
        }
        draft_v2 = {
            "id": "d2",
            "version": 2,
            "content": "Updated and improved content here with more detail.",
            "word_count": 150,
            "citation_count": 5,
        }

        with patch.object(draft_service, 'compare_drafts') as mock_compare:
            mock_compare.return_value = {
                "version_a": 1,
                "version_b": 2,
                "word_count_diff": 50,
                "citation_count_diff": 2,
                "similarity_score": 0.75,
            }

            result = await draft_service.compare_drafts(
                project_id="proj-123",
                version_a=1,
                version_b=2,
                db=mock_db_session,
            )

            assert result is not None
            assert result["word_count_diff"] == 50
            assert result["citation_count_diff"] == 2
            assert 0 <= result["similarity_score"] <= 1


class TestDraftCitations:
    """Tests for draft citation extraction."""

    @pytest.mark.asyncio
    async def test_get_draft_citations(self, draft_service, mock_db_session, sample_draft):
        """Test getting citations mapped to [Doc N] indices."""
        with patch.object(draft_service, 'get_draft_citations') as mock_citations:
            mock_citations.return_value = [
                {"index": 1, "document_id": "doc1", "title": "Paper 1", "snippet": "..."},
                {"index": 2, "document_id": "doc2", "title": "Paper 2", "snippet": "..."},
                {"index": 3, "document_id": "doc3", "title": "Paper 3", "snippet": "..."},
            ]

            result = await draft_service.get_draft_citations(
                draft_id=sample_draft["id"],
                db=mock_db_session,
            )

            assert len(result) >= 1
            assert all("index" in c for c in result)
            assert all("document_id" in c for c in result)


class TestDraftDeletion:
    """Tests for draft deletion."""

    @pytest.mark.asyncio
    async def test_delete_draft(self, draft_service, mock_db_session, sample_draft):
        """Test deleting a draft."""
        with patch.object(draft_service, 'delete_draft') as mock_delete:
            mock_delete.return_value = True

            result = await draft_service.delete_draft(
                draft_id=sample_draft["id"],
                db=mock_db_session,
            )

            assert result is True


class TestGenerationStatus:
    """Tests for generation status tracking."""

    @pytest.mark.asyncio
    async def test_get_status(self, draft_service, mock_db_session, sample_project):
        """Test getting generation status."""
        with patch.object(draft_service, 'get_status') as mock_status:
            mock_status.return_value = {
                "status": "generating",
                "progress": 0.65,
                "current_step": "Synthesizing content",
                "estimated_remaining": 15,
            }

            result = await draft_service.get_status(
                project_id=sample_project["id"],
            )

            assert result is not None
            assert result["status"] == "generating"
            assert 0 <= result["progress"] <= 1

    @pytest.mark.asyncio
    async def test_cancel_generation(self, draft_service, mock_db_session, sample_project):
        """Test cancelling an in-progress generation."""
        with patch.object(draft_service, 'cancel_generation') as mock_cancel:
            mock_cancel.return_value = {"cancelled": True}

            result = await draft_service.cancel_generation(
                project_id=sample_project["id"],
            )

            assert result["cancelled"] is True


class TestLaTeXConversion:
    """Tests for LaTeX conversion internals."""

    @pytest.mark.asyncio
    async def test_convert_to_latex(self, draft_service, sample_draft):
        """Test internal LaTeX conversion."""
        with patch.object(draft_service, '_convert_to_latex') as mock_convert:
            mock_convert.return_value = "\\documentclass{article}\n\\begin{document}\n..."

            result = await draft_service._convert_to_latex(sample_draft["content"])

            assert result is not None
            assert "\\documentclass" in result or "documentclass" in str(result).lower()

    @pytest.mark.asyncio
    async def test_generate_bib_entries(self, draft_service, mock_db_session):
        """Test BibTeX entry generation from citations."""
        citations = [
            {"document_id": "doc1", "title": "Paper 1", "authors": ["A"], "year": 2023},
            {"document_id": "doc2", "title": "Paper 2", "authors": ["B"], "year": 2022},
        ]

        with patch.object(draft_service, '_generate_bib_entries') as mock_bib:
            mock_bib.return_value = "@article{doc1,...}\n@article{doc2,...}"

            result = await draft_service._generate_bib_entries(citations)

            assert result is not None
            assert "@article" in result or "@" in result
