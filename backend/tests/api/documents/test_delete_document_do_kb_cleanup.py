"""Deleting a document must clean up its DO KB data source (audit B4).

Before this fix, `delete_document` / `bulk_delete_documents` soft-deleted the
Document but never removed its DO KB data source. Because
`resolve_and_filter_chunks` resolves chunks by `storage_path` + org and does
NOT filter `is_deleted`, the soft-deleted doc's chunks stayed live in the KB
index and kept surfacing in retrieval — plus the data source leaked storage on
DO's side.

The fix wires the existing `unsync_document_from_kb` helper into both delete
paths (after the commit, best-effort). Failure isolation is load-bearing: a KB
outage during delete must not raise or block the user's delete.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.documents import documents as documents_mod


def _result(value):
    r = MagicMock()
    r.scalars.return_value.first.return_value = value
    return r


def _make_document(*, ds_uuid: str | None = "ds-123"):
    document = MagicMock()
    document.id = uuid.uuid4()
    document.organization_id = uuid.uuid4()
    document.file_size_bytes = 100
    document.do_kb_data_source_uuid = ds_uuid
    # owner check: delete_document compares uploaded_by_user_id to current_user.id
    document.uploaded_by_user_id = "user-1"
    document.organization = MagicMock()
    return document


@pytest.mark.unit
def test_delete_document_unsyncs_do_kb_data_source():
    """A doc with a do_kb_data_source_uuid triggers unsync on delete."""
    document = _make_document(ds_uuid="ds-123")

    user = MagicMock()
    user.id = "user-1"
    user.has_permission.return_value = True
    org = MagicMock()
    org.id = document.organization_id

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[_result(document), _result(None), _result(None)]
    )
    db.commit = AsyncMock()

    file_service = MagicMock()

    unsync = AsyncMock(return_value=True)
    with patch("src.services.do_kb.unsync_document_from_kb", new=unsync):
        resp = asyncio.run(
            documents_mod.delete_document(
                document_id=str(document.id),
                cascade=True,
                current_user=user,
                organization=org,
                db=db,
                file_service=file_service,
            )
        )

    unsync.assert_awaited_once_with(db, document)
    assert resp["document_id"] == str(document.id)


@pytest.mark.unit
def test_delete_document_skips_unsync_when_no_data_source():
    """No do_kb_data_source_uuid → no unsync call (nothing to clean up)."""
    document = _make_document(ds_uuid=None)

    user = MagicMock()
    user.id = "user-1"
    user.has_permission.return_value = True
    org = MagicMock()
    org.id = document.organization_id

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[_result(document), _result(None), _result(None)]
    )
    db.commit = AsyncMock()

    unsync = AsyncMock(return_value=True)
    with patch("src.services.do_kb.unsync_document_from_kb", new=unsync):
        asyncio.run(
            documents_mod.delete_document(
                document_id=str(document.id),
                cascade=True,
                current_user=user,
                organization=org,
                db=db,
                file_service=MagicMock(),
            )
        )

    unsync.assert_not_awaited()


@pytest.mark.unit
def test_delete_document_do_kb_failure_does_not_block_delete():
    """A KB outage during unsync must not raise out of the delete endpoint."""
    document = _make_document(ds_uuid="ds-123")

    user = MagicMock()
    user.id = "user-1"
    user.has_permission.return_value = True
    org = MagicMock()
    org.id = document.organization_id

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[_result(document), _result(None), _result(None)]
    )
    db.commit = AsyncMock()

    # unsync_document_from_kb is documented never-raises, but defend the wire-in:
    # even if it blows up, the user's delete must still succeed.
    boom = AsyncMock(side_effect=RuntimeError("DO KB down"))
    with patch("src.services.do_kb.unsync_document_from_kb", new=boom):
        resp = asyncio.run(
            documents_mod.delete_document(
                document_id=str(document.id),
                cascade=True,
                current_user=user,
                organization=org,
                db=db,
                file_service=MagicMock(),
            )
        )

    assert resp["document_id"] == str(document.id)
    boom.assert_awaited_once()


@pytest.mark.unit
def test_bulk_delete_unsyncs_each_deleted_document():
    """Bulk delete unsyncs every doc that had a data source."""
    doc_a = _make_document(ds_uuid="ds-a")
    doc_b = _make_document(ds_uuid=None)  # no DS → skipped

    user = MagicMock()
    user.id = "user-1"
    user.has_permission.return_value = True  # ADMIN gate
    org = MagicMock()

    request = MagicMock()
    request.document_ids = [str(doc_a.id), str(doc_b.id)]

    db = MagicMock()
    # Per-doc: entity update, job update are execute() too; only the initial
    # doc-select returns a scalar we read. Use a mapping by call to stay robust.
    db.execute = AsyncMock(
        side_effect=[
            _result(doc_a),  # select doc_a
            MagicMock(),  # entity update
            MagicMock(),  # job update
            _result(doc_b),  # select doc_b
            MagicMock(),  # entity update
            MagicMock(),  # job update
        ]
    )
    db.commit = AsyncMock()

    unsync = AsyncMock(return_value=True)
    with patch("src.services.do_kb.unsync_document_from_kb", new=unsync):
        asyncio.run(
            documents_mod.bulk_delete_documents(
                request=request,
                cascade=True,
                current_user=user,
                organization=org,
                db=db,
                file_service=MagicMock(),
            )
        )

    # doc_a had a data source → unsynced; doc_b had none → skipped.
    unsync.assert_awaited_once_with(db, doc_a)


@pytest.mark.unit
def test_unsync_helper_nulls_uuid_and_swallows_do_failure():
    """The real unsync_document_from_kb clears the uuid even when the DO
    delete_data_source call fails, and never raises."""
    from src.services.do_kb import ingest as ingest_mod

    document = MagicMock()
    document.id = uuid.uuid4()
    document.organization_id = uuid.uuid4()
    document.do_kb_data_source_uuid = "ds-123"
    document.do_kb_indexed_at = "2026-01-01"
    document.do_kb_index_status = "indexed"

    session = MagicMock()
    session.commit = AsyncMock()

    # DO client whose delete_data_source blows up (KB outage).
    client = MagicMock()
    client.delete_data_source = AsyncMock(side_effect=RuntimeError("DO KB down"))

    fake_settings = MagicMock()
    fake_settings.DO_KB_ENABLED = True

    with (
        patch.object(ingest_mod, "settings", fake_settings),
        patch.object(
            ingest_mod, "ensure_kb_for_org", new=AsyncMock(return_value="kb-uuid")
        ),
    ):
        result = asyncio.run(
            ingest_mod.unsync_document_from_kb(session, document, client=client)
        )

    # DO delete failed → helper returns True only on a clean commit; regardless,
    # the stale uuid must be cleared so it doesn't linger, and it must not raise.
    assert document.do_kb_data_source_uuid is None
    assert document.do_kb_indexed_at is None
    assert document.do_kb_index_status is None
    session.commit.assert_awaited_once()
    assert result is True
