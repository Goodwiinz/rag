"""Regression coverage for shared arXiv persistence and deduplication."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from src.core.config import settings
from src.services.arxiv.persistence import persist_arxiv_documents
from tests.mocks.services import MockAsyncSession, MockResult

pytestmark = pytest.mark.unit


def _source(arxiv_id: str = "2401.00001v1") -> SimpleNamespace:
    return SimpleNamespace(
        title="Placeholder",
        content_text="paper content",
        content_summary=None,
        document_metadata={
            "arxiv_id": arxiv_id,
            "title": "  Durable\nPaper  ",
            "publication_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        },
    )


def _storage_fields(checksum: str = "abc123") -> dict[str, object]:
    return {
        "filename": "2401.00001v1.pdf",
        "file_size_bytes": 12,
        "mime_type": "application/pdf",
        "document_type": "PDF",
        "checksum_sha256": checksum,
        "file_path": "s3://bucket/key",
        "storage_backend": "s3",
        "storage_path": "key",
    }


async def test_exact_arxiv_replay_reuses_before_storage() -> None:
    existing_id = uuid4()
    db = MockAsyncSession().set_scalar_result(existing_id)

    with (
        patch("src.core.database.AsyncSessionLocal", return_value=db),
        patch.object(settings, "DO_KB_ENABLED", False),
        patch("src.services.arxiv.persistence.store_arxiv_pdf") as store,
    ):
        result = await persist_arxiv_documents(
            [_source()], user_id=uuid4(), organization_id=uuid4()
        )

    assert result.document_ids == [str(existing_id)]
    assert result.reused_document_ids == {str(existing_id)}
    assert db._added_items == []
    store.assert_not_called()


async def test_checksum_reuse_deletes_newly_promoted_object() -> None:
    existing_id = uuid4()
    db = MockAsyncSession()
    db.execute = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            MockResult(scalar_result=None),
            MockResult(scalar_result=existing_id),
        ]
    )
    storage_fields = _storage_fields()

    with (
        patch("src.core.database.AsyncSessionLocal", return_value=db),
        patch.object(settings, "DO_KB_ENABLED", False),
        patch(
            "src.services.arxiv.persistence.store_arxiv_pdf",
            return_value=storage_fields,
        ),
        patch("src.services.arxiv.persistence.delete_arxiv_storage") as delete,
    ):
        result = await persist_arxiv_documents(
            [_source()], user_id=uuid4(), organization_id=uuid4()
        )

    assert result.document_ids == [str(existing_id)]
    assert result.reused_document_ids == {str(existing_id)}
    assert db._added_items == []
    delete.assert_called_once_with(storage_fields)


async def test_new_document_is_durable_searchable_and_json_safe() -> None:
    db = MockAsyncSession()
    storage_fields = _storage_fields()
    update_vectors = AsyncMock()

    with (
        patch("src.core.database.AsyncSessionLocal", return_value=db),
        patch.object(settings, "DO_KB_ENABLED", False),
        patch(
            "src.services.arxiv.persistence.store_arxiv_pdf",
            return_value=storage_fields,
        ),
        patch(
            "src.services.search.fulltext_search_service.fulltext_search_service.async_update_document_search_vectors",
            update_vectors,
        ),
    ):
        result = await persist_arxiv_documents(
            [_source()], user_id="user-1", organization_id="org-A"
        )

    assert len(result.document_ids) == 1
    document = db._added_items[0]
    assert document.organization_id == "org-A"
    assert document.uploaded_by_user_id == "user-1"
    assert document.title == "Durable Paper"
    assert document.storage_backend == "s3"
    assert document.document_metadata["publication_date"] == "2024-01-01T00:00:00+00:00"
    update_vectors.assert_awaited_once_with([str(document.id)], db)


async def test_storage_promotion_runs_between_short_database_sessions() -> None:
    lookup_db = MockAsyncSession()
    write_db = MockAsyncSession()
    sessions = iter([lookup_db, write_db])

    def _store(*_args: object) -> dict[str, object]:
        assert lookup_db._closed is True
        assert write_db.execute_calls == []
        return _storage_fields()

    with (
        patch(
            "src.core.database.AsyncSessionLocal", side_effect=lambda: next(sessions)
        ),
        patch.object(settings, "DO_KB_ENABLED", False),
        patch("src.services.arxiv.persistence.store_arxiv_pdf", side_effect=_store),
        patch(
            "src.services.search.fulltext_search_service.fulltext_search_service.async_update_document_search_vectors",
            new_callable=AsyncMock,
        ),
    ):
        await persist_arxiv_documents(
            [_source()], user_id=uuid4(), organization_id=uuid4()
        )


async def test_transaction_failure_compensates_promoted_storage() -> None:
    db = MockAsyncSession()
    db.flush = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("database unavailable")
    )
    storage_fields = _storage_fields()

    with (
        patch("src.core.database.AsyncSessionLocal", return_value=db),
        patch.object(settings, "DO_KB_ENABLED", False),
        patch(
            "src.services.arxiv.persistence.store_arxiv_pdf",
            return_value=storage_fields,
        ),
        patch("src.services.arxiv.persistence.delete_arxiv_storage") as delete,
        pytest.raises(RuntimeError, match="database unavailable"),
    ):
        await persist_arxiv_documents(
            [_source()], user_id=uuid4(), organization_id=uuid4()
        )

    delete.assert_called_once_with(storage_fields)


async def test_concurrent_checksum_loser_reuses_winner_and_cleans_storage() -> None:
    winner_id = uuid4()
    db = MockAsyncSession()
    db.execute = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            MockResult(scalar_result=None),
            MockResult(scalar_result=None),
            MockResult(scalar_result=winner_id),
        ]
    )
    db.flush = AsyncMock(  # type: ignore[method-assign]
        side_effect=IntegrityError(
            "INSERT INTO documents", {}, Exception("uq_documents_org_checksum_live")
        )
    )
    storage_fields = _storage_fields()

    with (
        patch("src.core.database.AsyncSessionLocal", return_value=db),
        patch.object(settings, "DO_KB_ENABLED", False),
        patch(
            "src.services.arxiv.persistence.store_arxiv_pdf",
            return_value=storage_fields,
        ),
        patch("src.services.arxiv.persistence.delete_arxiv_storage") as delete,
    ):
        result = await persist_arxiv_documents(
            [_source()], user_id=uuid4(), organization_id=uuid4()
        )

    assert result.document_ids == [str(winner_id)]
    assert result.reused_document_ids == {str(winner_id)}
    delete.assert_called_once_with(storage_fields)


@pytest.mark.parametrize(
    ("sync_result", "expected_status", "expected_failed"),
    [("data-source-1", "completed", False), (None, "failed", True)],
)
async def test_kb_sync_outcome_is_persisted(
    sync_result: str | None, expected_status: str, expected_failed: bool
) -> None:
    db = MockAsyncSession()
    kb_db = MagicMock()
    kb_db.__aenter__ = AsyncMock(return_value=kb_db)
    kb_db.__aexit__ = AsyncMock(return_value=False)
    kb_db.merge = AsyncMock(side_effect=lambda document: document)
    kb_db.commit = AsyncMock()
    sessions = iter([db, db, kb_db])

    with (
        patch(
            "src.core.database.AsyncSessionLocal", side_effect=lambda: next(sessions)
        ),
        patch.object(settings, "DO_KB_ENABLED", True),
        patch(
            "src.services.arxiv.persistence.store_arxiv_pdf",
            return_value=_storage_fields(),
        ),
        patch(
            "src.services.search.fulltext_search_service.fulltext_search_service.async_update_document_search_vectors",
            new_callable=AsyncMock,
        ),
        patch(
            "src.services.do_kb.sync_documents_to_kb",
            new_callable=AsyncMock,
            return_value=[sync_result],
        ),
    ):
        result = await persist_arxiv_documents(
            [_source()], user_id=uuid4(), organization_id=uuid4()
        )

    assert db._added_items[0].do_kb_sync_status == expected_status
    assert result.kb_sync_failed is expected_failed
    assert kb_db.commit.await_count == 2


async def test_kb_exception_marks_document_reconcilable() -> None:
    db = MockAsyncSession()
    kb_db = MagicMock()
    kb_db.__aenter__ = AsyncMock(return_value=kb_db)
    kb_db.__aexit__ = AsyncMock(return_value=False)
    kb_db.merge = AsyncMock(side_effect=lambda document: document)
    kb_db.commit = AsyncMock()
    sessions = iter([db, db, kb_db])

    with (
        patch(
            "src.core.database.AsyncSessionLocal", side_effect=lambda: next(sessions)
        ),
        patch.object(settings, "DO_KB_ENABLED", True),
        patch(
            "src.services.arxiv.persistence.store_arxiv_pdf",
            return_value=_storage_fields(),
        ),
        patch(
            "src.services.search.fulltext_search_service.fulltext_search_service.async_update_document_search_vectors",
            new_callable=AsyncMock,
        ),
        patch(
            "src.services.do_kb.sync_documents_to_kb",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DO unavailable"),
        ),
    ):
        result = await persist_arxiv_documents(
            [_source()], user_id=uuid4(), organization_id=uuid4()
        )

    assert db._added_items[0].do_kb_sync_status == "failed"
    assert result.kb_sync_failed is True
    assert kb_db.commit.await_count == 2
