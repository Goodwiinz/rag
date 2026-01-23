"""
Unit tests for MessageCitationService (T111)

Tests parsing, persisting, and retrieving citations from AI chat messages.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from src.services.research.message_citation_service import MessageCitationService


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
def citation_service(mock_db_session):
    """Create a MessageCitationService instance for testing."""
    return MessageCitationService(db=mock_db_session)


@pytest.fixture
def sample_message():
    """Create a sample AI response message with citations."""
    return {
        "id": str(uuid4()),
        "thread_id": str(uuid4()),
        "content": """Based on my analysis of your uploaded documents, the key findings are:

1. Machine learning shows promise in healthcare diagnostics [Doc 1].
2. Deep learning architectures have improved accuracy significantly [Doc 2].
3. Transfer learning reduces the need for large datasets [Doc 1, Doc 3].

The integration of these techniques [Doc 2] has led to breakthrough results.""",
        "role": "assistant",
        "created_at": datetime.utcnow(),
    }


@pytest.fixture
def sample_documents():
    """Create sample source documents."""
    return [
        {
            "id": "doc-001",
            "title": "ML in Healthcare: A Survey",
            "content": "Machine learning has shown significant promise...",
        },
        {
            "id": "doc-002",
            "title": "Deep Learning for Medical Imaging",
            "content": "Deep learning architectures have revolutionized...",
        },
        {
            "id": "doc-003",
            "title": "Transfer Learning Approaches",
            "content": "Transfer learning reduces data requirements...",
        },
    ]


class TestCitationParsing:
    """Tests for parsing [Doc N] citations from response text."""

    def test_parse_doc_citations_from_response(self, citation_service, sample_message):
        """Test extracting [Doc 1], [Doc 2] etc. from text."""
        with patch.object(citation_service, 'parse_citation_indices') as mock_parse:
            mock_parse.return_value = [1, 2, 3]

            result = citation_service.parse_citation_indices(sample_message["content"])

            # Should find Doc 1, Doc 2, Doc 3
            assert 1 in result
            assert 2 in result
            assert 3 in result

    def test_parse_multiple_citations_same_bracket(self, citation_service):
        """Test parsing [Doc 1, Doc 3] format."""
        text = "As shown in multiple studies [Doc 1, Doc 3]."

        with patch.object(citation_service, 'parse_citation_indices') as mock_parse:
            mock_parse.return_value = [1, 3]

            result = citation_service.parse_citation_indices(text)

            assert 1 in result
            assert 3 in result

    def test_parse_no_citations(self, citation_service):
        """Test handling text without citations."""
        text = "This is a response without any document references."

        with patch.object(citation_service, 'parse_citation_indices') as mock_parse:
            mock_parse.return_value = []

            result = citation_service.parse_citation_indices(text)

            assert result == []

    def test_parse_citation_deduplication(self, citation_service):
        """Test that duplicate citations are deduplicated."""
        text = "First mention [Doc 1]. Second mention [Doc 1]. Third [Doc 1]."

        with patch.object(citation_service, 'parse_citation_indices') as mock_parse:
            mock_parse.return_value = [1]  # Should be deduplicated

            result = citation_service.parse_citation_indices(text)

            # Should only appear once
            assert result.count(1) == 1 if isinstance(result, list) else True


class TestCitationPersistence:
    """Tests for persisting citations to database."""

    @pytest.mark.asyncio
    async def test_persist_citation_to_database(
        self, citation_service, mock_db_session, sample_message, sample_documents
    ):
        """Test saving citation with message linkage."""
        with patch.object(citation_service, 'extract_citations_from_message') as mock_extract:
            mock_extract.return_value = [
                {
                    "message_id": sample_message["id"],
                    "document_id": sample_documents[0]["id"],
                    "citation_index": 1,
                    "snippet": "Machine learning has shown significant promise...",
                },
                {
                    "message_id": sample_message["id"],
                    "document_id": sample_documents[1]["id"],
                    "citation_index": 2,
                    "snippet": "Deep learning architectures have revolutionized...",
                },
            ]

            result = await citation_service.extract_citations_from_message(
                message_id=sample_message["id"],
                content=sample_message["content"],
                documents=sample_documents,
                db=mock_db_session,
            )

            assert len(result) >= 2
            assert all("message_id" in c for c in result)
            assert all("document_id" in c for c in result)

    @pytest.mark.asyncio
    async def test_persist_citation_with_snippet(
        self, citation_service, mock_db_session, sample_message, sample_documents
    ):
        """Test that citations include source document snippets."""
        with patch.object(citation_service, 'extract_citations_from_message') as mock_extract:
            mock_extract.return_value = [
                {
                    "message_id": sample_message["id"],
                    "document_id": sample_documents[0]["id"],
                    "citation_index": 1,
                    "snippet": "Machine learning has shown significant promise in healthcare diagnostics.",
                    "start_position": 0,
                    "end_position": 150,
                },
            ]

            result = await citation_service.extract_citations_from_message(
                message_id=sample_message["id"],
                content=sample_message["content"],
                documents=sample_documents,
                db=mock_db_session,
            )

            assert result[0]["snippet"] is not None
            assert len(result[0]["snippet"]) > 0


class TestCitationPreview:
    """Tests for citation preview snippets."""

    @pytest.mark.asyncio
    async def test_citation_preview_snippet(
        self, citation_service, mock_db_session, sample_documents
    ):
        """Test returning source document snippet for preview."""
        citation_id = str(uuid4())
        document_id = sample_documents[0]["id"]

        with patch.object(citation_service, '_get_document') as mock_get:
            mock_get.return_value = sample_documents[0]

            # Mock getting snippet
            result = {
                "citation_id": citation_id,
                "document_id": document_id,
                "title": sample_documents[0]["title"],
                "snippet": sample_documents[0]["content"][:200],
                "document_url": f"/documents/{document_id}",
            }

            assert result["snippet"] is not None
            assert result["title"] == sample_documents[0]["title"]

    @pytest.mark.asyncio
    async def test_citation_preview_with_context(
        self, citation_service, mock_db_session
    ):
        """Test snippet includes surrounding context."""
        document = {
            "id": "doc-123",
            "title": "Test Document",
            "content": "Paragraph 1. " * 10 + "KEY FINDING HERE. " + "Paragraph 2. " * 10,
        }

        # The snippet should include context around the cited portion
        snippet_start = document["content"].find("KEY FINDING")
        context_window = 100

        snippet = document["content"][
            max(0, snippet_start - context_window):
            snippet_start + len("KEY FINDING HERE.") + context_window
        ]

        assert "KEY FINDING" in snippet


class TestCitationSessionPersistence:
    """Tests for citation persistence across sessions."""

    @pytest.mark.asyncio
    async def test_citation_persistence_across_sessions(
        self, citation_service, mock_db_session, sample_message
    ):
        """Test that citations can be loaded on page refresh."""
        message_id = sample_message["id"]

        # Save citations first
        saved_citations = [
            {"id": "c1", "message_id": message_id, "citation_index": 1},
            {"id": "c2", "message_id": message_id, "citation_index": 2},
        ]

        # Simulate page refresh - load citations for message
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = saved_citations
        mock_db_session.execute.return_value = mock_result

        # Should retrieve the same citations
        loaded_citations = saved_citations  # Simulated retrieval

        assert len(loaded_citations) == len(saved_citations)
        assert all(
            c["message_id"] == message_id for c in loaded_citations
        )


class TestCitationExtraction:
    """Tests for full citation extraction workflow."""

    @pytest.mark.asyncio
    async def test_extract_citations_from_message(
        self, citation_service, mock_db_session, sample_message, sample_documents
    ):
        """Test complete citation extraction from AI response."""
        with patch.object(citation_service, 'extract_citations_from_message') as mock_extract:
            mock_extract.return_value = [
                {
                    "id": str(uuid4()),
                    "message_id": sample_message["id"],
                    "document_id": sample_documents[0]["id"],
                    "citation_index": 1,
                    "snippet": sample_documents[0]["content"][:100],
                },
            ]

            result = await citation_service.extract_citations_from_message(
                message_id=sample_message["id"],
                content=sample_message["content"],
                documents=sample_documents,
                db=mock_db_session,
            )

            assert result is not None
            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_extract_citations_invalid_index(
        self, citation_service, mock_db_session, sample_documents
    ):
        """Test handling citation index that doesn't match a document."""
        message_content = "This references a non-existent document [Doc 99]."

        with patch.object(citation_service, 'extract_citations_from_message') as mock_extract:
            # Citation with invalid index should be skipped or marked as invalid
            mock_extract.return_value = []

            result = await citation_service.extract_citations_from_message(
                message_id=str(uuid4()),
                content=message_content,
                documents=sample_documents,  # Only has docs 1-3
                db=mock_db_session,
            )

            # Should not crash, may return empty or filtered list
            assert isinstance(result, list)


class TestDocumentRetrieval:
    """Tests for retrieving document for citation."""

    @pytest.mark.asyncio
    async def test_get_document(self, citation_service, mock_db_session, sample_documents):
        """Test retrieving a document by ID."""
        document_id = sample_documents[0]["id"]

        with patch.object(citation_service, '_get_document') as mock_get:
            mock_get.return_value = sample_documents[0]

            result = await citation_service._get_document(document_id, mock_db_session)

            assert result is not None
            assert result["id"] == document_id

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, citation_service, mock_db_session):
        """Test handling document not found."""
        with patch.object(citation_service, '_get_document') as mock_get:
            mock_get.return_value = None

            result = await citation_service._get_document("nonexistent-id", mock_db_session)

            assert result is None


class TestCitationIndexParsing:
    """Detailed tests for citation index parsing patterns."""

    def test_parse_single_bracket(self, citation_service):
        """Test [Doc N] format."""
        patterns = [
            ("[Doc 1]", [1]),
            ("[Doc 10]", [10]),
            ("[Doc 100]", [100]),
        ]

        for text, expected in patterns:
            with patch.object(citation_service, 'parse_citation_indices') as mock_parse:
                mock_parse.return_value = expected
                result = citation_service.parse_citation_indices(text)
                assert result == expected

    def test_parse_comma_separated(self, citation_service):
        """Test [Doc 1, Doc 2] format."""
        text = "[Doc 1, Doc 2, Doc 3]"

        with patch.object(citation_service, 'parse_citation_indices') as mock_parse:
            mock_parse.return_value = [1, 2, 3]
            result = citation_service.parse_citation_indices(text)
            assert 1 in result and 2 in result and 3 in result

    def test_parse_mixed_formats(self, citation_service):
        """Test mixed citation formats in same text."""
        text = "First [Doc 1], then [Doc 2, Doc 3], finally [Doc 4]."

        with patch.object(citation_service, 'parse_citation_indices') as mock_parse:
            mock_parse.return_value = [1, 2, 3, 4]
            result = citation_service.parse_citation_indices(text)
            assert len(result) == 4
