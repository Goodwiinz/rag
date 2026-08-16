"""The tracker must not recreate the legacy zero-byte arXiv row shape."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.arxiv.arxiv_change_tracker import ArXivChangeTracker
from src.services.arxiv.persistence import ArxivPersistenceResult

pytestmark = pytest.mark.unit


async def test_new_paper_delegates_to_shared_durable_persistence() -> None:
    tracker = object.__new__(ArXivChangeTracker)
    persist = AsyncMock(
        return_value=ArxivPersistenceResult(
            document_ids=["document-1"], reused_document_ids=set()
        )
    )
    paper = {
        "id": "2401.00001v1",
        "title": "Durable paper",
        "abstract": "Useful abstract",
        "authors": ["Researcher"],
    }

    with patch("src.services.arxiv.persistence.persist_arxiv_documents", persist):
        await tracker._ingest_new_paper(
            paper,
            organization_id="org-A",
            user_id="user-1",
            update_kg=False,
        )

    assert persist.await_args is not None
    source = persist.await_args.args[0][0]
    assert source.document_metadata["arxiv_id"] == "2401.00001v1"
    assert source.content_text == "Useful abstract"
    persist.assert_awaited_once_with(
        [source], user_id="user-1", organization_id="org-A"
    )


async def test_force_update_refreshes_text_and_search_vector() -> None:
    from src.models.document import Document

    tracker = object.__new__(ArXivChangeTracker)
    document = Document(
        id=uuid4(),
        arxiv_id=None,
        title="Old title",
        content_text="Old abstract",
        document_metadata={"arxiv_id": "2401.00001v1"},
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = document
    db = AsyncMock()
    db.execute.return_value = result
    update_vectors = AsyncMock()
    paper = {
        "id": "2401.00001v1",
        "title": "New title",
        "abstract": "New abstract",
    }

    with patch(
        "src.services.search.fulltext_search_service.fulltext_search_service.async_update_document_search_vectors",
        update_vectors,
    ):
        await tracker._update_existing_paper(db, paper, ["force_update"], "org-A")

    assert document.arxiv_id == paper["id"]
    assert document.title == "New title"
    assert document.content_text == "New abstract"
    update_vectors.assert_awaited_once_with([str(document.id)], db)
    db.commit.assert_awaited_once()
