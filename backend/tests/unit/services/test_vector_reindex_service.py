from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.models.vector import VectorOperationResult
from src.services.search.vector_search_service import VectorSearchService


def test_reindex_all_content_arxiv_only_processes_matching_documents() -> None:
    service = VectorSearchService()

    arxiv_doc = SimpleNamespace(
        id="doc-arxiv",
        title="ArXiv Paper: 2512.12345",
        content_text="full content",
        document_type="pdf",
        document_metadata={"arxiv_id": "2512.12345", "source": "arxiv"},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    non_arxiv_doc = SimpleNamespace(
        id="doc-other",
        title="Other Paper",
        content_text="other content",
        document_type="pdf",
        document_metadata={"source": "upload"},
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    service._load_documents_for_reindex = MagicMock(
        return_value=[arxiv_doc, non_arxiv_doc]
    )
    service.delete_document_vectors = MagicMock(
        return_value=VectorOperationResult(success=True, message="ok", processing_time=0.0)
    )
    service.index_document = MagicMock(
        return_value=VectorOperationResult(success=True, message="ok", processing_time=0.0)
    )

    result = service.reindex_all_content(
        organization_id="org-1", batch_size=10, arxiv_only=True
    )

    assert result["total_candidates"] == 1
    assert result["processed"] == 1
    assert result["succeeded"] == 1
    service.delete_document_vectors.assert_called_once_with("doc-arxiv")
    service.index_document.assert_called_once()
