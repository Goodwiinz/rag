"""DB-audit regressions: delete ordering, atomic quota, dedup-race 409.

- delete_document must commit the soft-delete BEFORE removing the storage
  object (mirrors FileService.delete_file's fix; the endpoint used to bypass it).
- Organization storage accounting must be a single server-side UPDATE, not a
  Python read-modify-write (lost updates under concurrency).
- A concurrent duplicate upload that loses the check-then-insert race hits the
  uq_documents_org_checksum_live unique index; upload_file must map that
  IntegrityError to the same 409 as the pre-check.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.api.documents import documents as documents_mod
from src.models.document import DocumentType
from src.models.organization import Organization
from src.services.documents.enhanced_file_service import EnhancedFileService

pytestmark = pytest.mark.unit


def _result(value):
    r = MagicMock()
    r.scalars.return_value.first.return_value = value
    return r


def _doc():
    document = MagicMock()
    document.id = uuid.uuid4()
    document.organization_id = uuid.uuid4()
    document.file_size_bytes = 100
    document.do_kb_data_source_uuid = None
    document.uploaded_by_user_id = "user-1"
    return document


def _user_org(document):
    user = MagicMock()
    user.id = "user-1"
    user.has_permission.return_value = True
    org = MagicMock()
    org.id = document.organization_id
    return user, org


def _delete(document, db, file_service):
    user, org = _user_org(document)
    return documents_mod.delete_document(
        document_id=str(document.id),
        cascade=True,
        current_user=user,
        organization=org,
        db=db,
        file_service=file_service,
    )


def test_commit_happens_before_physical_delete():
    document = _doc()
    order = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(document))
    db.commit = AsyncMock(side_effect=lambda: order.append("commit"))
    file_service = MagicMock()
    file_service.delete_physical_file = MagicMock(
        side_effect=lambda d: order.append("physical")
    )

    resp = asyncio.run(_delete(document, db, file_service))
    assert resp["document_id"] == str(document.id)
    assert order == ["commit", "physical"]


def test_commit_failure_leaves_object_untouched():
    document = _doc()
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(document))
    db.commit = AsyncMock(side_effect=RuntimeError("pool gone"))
    db.rollback = AsyncMock()
    file_service = MagicMock()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_delete(document, db, file_service))
    assert exc.value.status_code == 500
    # The rolled-back row is still live, so its object must NOT be deleted.
    file_service.delete_physical_file.assert_not_called()


def test_physical_delete_failure_does_not_fail_the_delete():
    document = _doc()
    db = MagicMock()
    db.execute = AsyncMock(return_value=_result(document))
    db.commit = AsyncMock()
    file_service = MagicMock()
    file_service.delete_physical_file = MagicMock(side_effect=RuntimeError("s3 down"))

    resp = asyncio.run(_delete(document, db, file_service))
    # Orphan object, not a failed delete: the committed soft-delete stands.
    assert resp["document_id"] == str(document.id)


def test_storage_usage_update_is_server_side_atomic():
    stmt = Organization.storage_usage_update(uuid.uuid4(), -100)
    sql = str(stmt.compile(compile_kwargs={"literal_binds": False})).lower()
    # Arithmetic + clamp happen inside the UPDATE, not in Python.
    assert "greatest" in sql
    assert "storage_used_bytes +" in sql.replace("organizations.storage_used_bytes", "storage_used_bytes")


def test_upload_dedup_race_maps_integrity_error_to_409():
    svc = object.__new__(EnhancedFileService)  # skip filesystem __init__
    svc._storage_backend = "s3"
    svc._s3_helper = MagicMock()  # backs the lazy s3_helper property
    svc.db = MagicMock()
    svc.db.commit = MagicMock(
        side_effect=IntegrityError(
            "INSERT INTO documents ...",
            {},
            Exception(
                'duplicate key value violates unique constraint '
                '"uq_documents_org_checksum_live"'
            ),
        )
    )
    svc._find_org_duplicate = MagicMock(return_value=None)  # race: check passed
    svc._best_effort_delete_object = MagicMock()

    file = MagicMock()
    file.filename = "paper.pdf"
    file.read = AsyncMock(return_value=b"content")
    user = MagicMock(id=uuid.uuid4())
    org = MagicMock(id=uuid.uuid4())
    validation_result = {
        "basic_validation": {
            "detected_mime_type": "application/pdf",
            "file_size": 7,
            "document_type": DocumentType.PDF,
        },
        "security_scan": {},
        "integrity_check": {},
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            svc.upload_file(
                file=file,
                title="t",
                description=None,
                user=user,
                organization=org,
                tags=[],
                is_public=False,
                custom_metadata={},
                validation_result=validation_result,
            )
        )
    assert exc.value.status_code == 409
    # The loser's already-uploaded object gets cleaned up.
    svc._best_effort_delete_object.assert_called_once()
